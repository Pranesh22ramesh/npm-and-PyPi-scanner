import pandas as pd, numpy as np, json
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score

SEEDS=(42,7,123); RATIO=3.0

# primary sets
c=pd.read_csv('features_v6_clean.csv',dtype={'package':str,'ecosystem':str,'version_after':str,'version_before':str})
k=pd.read_csv('features_v6_controls.csv',dtype={'package':str,'ecosystem':str,'version_after':str,'version_before':str})
c['label']=c.label.astype(int); k['label']=0
# v4 has TRUE predecessor features
v4=pd.read_csv('features_v4_balanced.csv',dtype={'package':str,'ecosystem':str,'version_after':str})
v4['label']=v4.label.astype(int)

BEFORE=['entropy_before','ast_nodes_before']
DELTA=[x for x in v4.columns if x.startswith('delta_')]
NORM =[x for x in v4.columns if x.startswith('norm_after_')]
AFTER_ABS=[x for x in v4.columns if x.startswith('after_')]+['entropy_after','ast_nodes_after','size_kb_after']
PRED_TRUE=BEFORE+DELTA   # genuinely predecessor-dependent

def kf(d): return d.package.astype(str)+'|'+d.ecosystem.astype(str)+'|'+d.version_after.astype(str)

# merge v4 predecessor+candidate features onto primary malicious via key
v4_feat=v4[['package','ecosystem','version_after']+NORM+AFTER_ABS+BEFORE+DELTA].copy()
v4_feat['__k']=kf(v4_feat)
v4_feat=v4_feat.drop_duplicates('__k')

# For controls we need the same feature space. v4 negatives include matched/post-incident negatives.
# Build candidate + predecessor features for controls too, from v4 negatives.
v4neg=v4[v4.label==0].copy()
# We'll size-match malicious (from primary c) to controls, but controls must have v4 feature vectors.
# Use v4's own negatives as the control pool (they have predecessor features), size-match on ast_nodes_after.
mal=c[c.label==1].copy(); mal['__k']=kf(mal)
mal=mal.merge(v4_feat.drop(columns=['package','ecosystem','version_after']),on='__k',how='inner')
print("primary malicious with true predecessor features:",len(mal))

pool=v4neg.copy()
# size proxy present in v4:
SIZE='ast_nodes_after'
def matched(mal,pool,seed,ratio=RATIO):
    p=pool.copy(); p['_u']=False; pick=[]
    ml=mal.sample(frac=1,random_state=seed)
    for _,r in ml.iterrows():
        cand=p[(p.ecosystem==r.ecosystem)&(~p._u)]
        if not len(cand): continue
        dd=(np.log1p(cand[SIZE].astype(float))-np.log1p(float(r[SIZE]))).abs()
        j=dd.idxmin()
        if dd.loc[j]>np.log(ratio): continue
        p.loc[j,'_u']=True; pick.append(j)
    return p.loc[pick].drop(columns='_u')

CAND=NORM+AFTER_ABS      # candidate-only (no predecessor)
FULL=CAND+PRED_TRUE      # + true predecessor context

def run(cols,split,seed,shuffle_pred=False,drop_pred=False,wrong_pred=False):
    ctrl=matched(mal,pool,seed)
    mm=pd.concat([mal[cols+['package','ecosystem','label']],
                  ctrl[cols+['package','ecosystem','label']]],ignore_index=True,sort=False)
    mm['label']=mm.label.astype(int)
    X=mm[cols].astype(float).fillna(0).copy(); y=mm.label.values; g=mm.package.values
    if shuffle_pred:
        rng=np.random.RandomState(seed); idx=rng.permutation(len(X))
        for col in cols:
            if col in PRED_TRUE: X[col]=X[col].values[idx]
    if drop_pred:
        for col in cols:
            if col in PRED_TRUE: X[col]=0.0
    if wrong_pred:
        rng=np.random.RandomState(seed+99)
        for eco in mm.ecosystem.unique():
            m=(mm.ecosystem==eco).values; perm=rng.permutation(np.where(m)[0])
            for col in cols:
                if col in PRED_TRUE:
                    vals=X[col].values.copy(); vals[np.where(m)[0]]=X[col].values[perm]; X[col]=vals
    Xv=X.values
    sp=(StratifiedKFold(5,shuffle=True,random_state=seed).split(Xv,y) if split=='random'
        else StratifiedGroupKFold(5,shuffle=True,random_state=seed).split(Xv,y,g))
    oof=np.zeros(len(mm))
    for tr,te in sp:
        pos=y[tr].sum(); w=np.where(y[tr]==1,(len(tr)-pos)/max(pos,1),1.0)
        m=HistGradientBoostingClassifier(max_iter=300,random_state=seed).fit(Xv[tr],y[tr],sample_weight=w)
        oof[te]=m.predict_proba(Xv[te])[:,1]
    return average_precision_score(y,oof), y.mean(), len(mm)

def ms(fn): 
    r=[fn(s) for s in SEEDS]; return round(np.mean([x[0] for x in r]),4),round(np.std([x[0] for x in r]),4),r[0][2],round(r[0][1],3)

R={"dataset":"PRIMARY malicious (360) + v4 size-matched negatives, TRUE predecessor features (entropy_before, ast_nodes_before, delta_*)",
   "seeds":list(SEEDS),"n_malicious":int(len(mal))}
for split in ["package_grouped","random"]:
    cand=ms(lambda s:run(CAND,split,s))
    full=ms(lambda s:run(FULL,split,s))
    shuf=ms(lambda s:run(FULL,split,s,shuffle_pred=True))
    wrong=ms(lambda s:run(FULL,split,s,wrong_pred=True))
    nop=ms(lambda s:run(FULL,split,s,drop_pred=True))
    R[split]={"n":cand[2],"prevalence":cand[3],
      "candidate_only":cand[0],"correct":full[0],"shuffled":shuf[0],
      "wrong_package":wrong[0],"no_predecessor":nop[0],
      "gain_vs_shuffled":round(full[0]-shuf[0],4),"gain_vs_candidate":round(full[0]-cand[0],4)}
    print(f"[{split}] n={cand[2]} prev={cand[3]} cand={cand[0]} correct={full[0]} shuf={shuf[0]} wrong={wrong[0]} nopred={nop[0]}")
    print(f"          gain vs shuffled = {full[0]-shuf[0]:+.4f} | gain vs candidate = {full[0]-cand[0]:+.4f}")
json.dump(R,open('/mnt/user-data/outputs/version_context_TRUE_primary.json','w'),indent=2)
print("\nsaved version_context_TRUE_primary.json")
