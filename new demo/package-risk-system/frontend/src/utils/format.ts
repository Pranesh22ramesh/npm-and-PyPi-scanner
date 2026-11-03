export const percent = (value:number|undefined|null) => value==null?'—':`${(value*100).toFixed(2)}%`
export const date = (value:string) => new Date(value).toLocaleString()
export const title = (value:string) => value.replaceAll('_',' ').replaceAll('-',' ')
