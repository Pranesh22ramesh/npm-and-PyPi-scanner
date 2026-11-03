import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter,NavLink,Route,Routes,Link } from 'react-router-dom'
import { Activity,BookOpen,Boxes,ChartNoAxesCombined,Database,FlaskConical,History,LayoutDashboard,ShieldCheck } from 'lucide-react'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Train from './pages/Train'
import Analyze from './pages/Analyze'
import FeatureUpload from './pages/FeatureUpload'
import NpmScan from './pages/NpmScan'
import PypiScan from './pages/PypiScan'
import Result from './pages/Result'
import ModelMetrics from './pages/ModelMetrics'
import HistoryPage from './pages/History'
import About from './pages/About'
import './styles.css'

const navigation=[['/','Overview',ShieldCheck],['/dashboard','Dashboard',LayoutDashboard],['/analyze','Analyze package',Boxes],['/history','Scan history',History],['/train','Train model',Database],['/metrics','Model performance',ChartNoAxesCombined],['/about','About the research',BookOpen]] as const
function App(){return <div className="app-shell"><aside className="sidebar"><Link to="/" className="brand"><span className="brand-icon"><ShieldCheck size={26}/></span><div>Package Risk<small>RESEARCH WORKBENCH</small></div></Link><div className="workspace-label">WORKSPACE</div><nav>{navigation.map(([path,label,Icon])=><NavLink key={path} to={path} end={path==='/'}><Icon size={19}/>{label}</NavLink>)}</nav><div className="sidebar-note"><FlaskConical size={22}/><strong>Research, with context.</strong><p>Package-level screening through version history.</p><span>RF + XGBoost · v1.0</span></div></aside><div className="workspace"><header className="topbar"><span><Activity size={17}/> Software supply-chain research</span><span className="static-tag">STATIC ANALYSIS ONLY</span></header><main><Routes><Route path="/" element={<Home/>}/><Route path="/dashboard" element={<Dashboard/>}/><Route path="/train" element={<Train/>}/><Route path="/analyze" element={<Analyze/>}/><Route path="/features" element={<FeatureUpload/>}/><Route path="/npm" element={<NpmScan/>}/><Route path="/pypi" element={<PypiScan/>}/><Route path="/result/:id" element={<Result/>}/><Route path="/result/:id/history" element={<Result history/>}/><Route path="/metrics" element={<ModelMetrics/>}/><Route path="/history" element={<HistoryPage/>}/><Route path="/about" element={<About/>}/><Route path="*" element={<div className="panel"><h1>Page not found</h1><Link to="/">Return to overview</Link></div>}/></Routes></main><footer>Package Risk Research Workbench <span>Screening signals. Evidence in context.</span></footer></div></div>}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><App/></BrowserRouter></React.StrictMode>)
