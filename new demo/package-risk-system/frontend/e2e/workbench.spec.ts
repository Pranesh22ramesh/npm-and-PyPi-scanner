import {test,expect} from '@playwright/test'
import path from 'node:path'

test('all research pages render and responsive overview fits',async({page})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message))
  for(const [route,title] of [['/','Multi-Version Package Risk Analysis'],['/dashboard','Screening dashboard'],['/train','Train the research model'],['/analyze','Analyze a package'],['/features','Upload version-pair features'],['/npm','Scan an npm package'],['/pypi','Scan a PyPI package'],['/metrics','Model performance'],['/history','Scan history'],['/about','About the research']]){
    await page.goto(route);await expect(page.getByRole('heading',{name:title,exact:true})).toBeVisible()
    await expect(page.locator('.notice.error')).toHaveCount(0)
  }
  await page.goto('/');await page.screenshot({path:'test-results/overview-desktop.png',fullPage:true})
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/overview-mobile.png',fullPage:true})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy()
  expect(errors).toEqual([])
})

test('feature CSV predicts, result evidence and version history work',async({page})=>{
  await page.goto('/features')
  await page.locator('input[type=file]').setInputFiles(path.resolve('../examples/new_package_features.csv'))
  await page.getByRole('button',{name:'Analyze feature CSV'}).click()
  await expect(page.getByRole('heading',{name:'Package Risk Screening Results'})).toBeVisible()
  await page.getByRole('link',{name:'is-number',exact:true}).click()
  await expect(page.getByRole('heading',{name:'Package Risk Screening Result',exact:true})).toBeVisible()
  await expect(page.getByText('Model score — not calibrated probability.',{exact:true})).toBeVisible()
  await expect(page.getByRole('heading',{name:'Model-associated indicators'})).toBeVisible()
  await page.screenshot({path:'test-results/analysis-result.png',fullPage:true})
  await page.getByRole('link',{name:'View version history'}).click()
  await expect(page.getByRole('heading',{name:'Package History',exact:true})).toBeVisible()
  await expect(page.locator('.timeline-item')).toHaveCount(2)
})

test('training schema validation and error display',async({page})=>{
  await page.goto('/train')
  await page.locator('input[type=file]').setInputFiles(path.resolve('../dataset/primary_size_matched_dataset.csv'))
  await page.getByRole('button',{name:'Validate schema'}).click()
  await expect(page.getByRole('button',{name:'Train & evaluate'})).toBeEnabled()
  await page.goto('/features')
  await page.locator('input[type=file]').setInputFiles({name:'invalid.csv',mimeType:'text/csv',buffer:Buffer.from('package,previous_version,current_version\ndemo,1,2')})
  await page.getByRole('button',{name:'Analyze feature CSV'}).click()
  await expect(page.getByRole('alert')).toContainText('Missing columns')
})

test('live npm registry analysis reaches trained ensemble',async({page})=>{
  await page.goto('/npm')
  await page.getByLabel('Package name',{exact:true}).fill('is-number')
  await page.getByRole('button',{name:'Fetch version history'}).click()
  await expect(page.getByRole('heading',{name:'Available release history'})).toBeVisible()
  await page.getByRole('button',{name:'Analyze recent releases'}).click()
  await expect(page.getByRole('heading',{name:'Package Risk Screening Result',exact:true})).toBeVisible({timeout:50000})
})
