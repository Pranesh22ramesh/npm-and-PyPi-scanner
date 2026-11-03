export type Indicator = {feature:string;importance:number;value:number}
export type Pair = {previous_version:string;current_version:string;status:string;observations:string[];features:Record<string,number>}
export type Scan = {id:string;package:string;registry:string;prediction:string;model_score:number;random_forest_score:number;xgboost_score:number;version_pairs_used:number;model_version:string;created_at:string;warning:string;interpretation:string;score_notice:string;indicator_notice:string;indicators:Indicator[];version_pairs:Pair[]}
export type Metric = {mean:number;std:number;min:number;max:number}
export type Metadata = {model_name:string;model_version:string;training_date:string;source_dataset_name:string;version_pair_count:number;package_count:number;raw_feature_count:number;aggregated_feature_count:number;evaluation_metrics:Record<string,Metric>;feature_importance:Indicator[];original_feature_names:string[];aggregated_feature_names:string[];aggregation_order:string[];seed42_confusion_matrix:number[][];std_ddof:number;extractor_provenance:{repository:string;commit:string;source:string};library_versions:Record<string,string>}
export type ModelInfo = {ready:boolean;error:string|null;metadata:Metadata|null;extractor:{enabled:boolean;reason:string|null};max_recent_versions:number}
export type Job<T> = {job_id?:string;id:string;status:string;message:string;result:T}
