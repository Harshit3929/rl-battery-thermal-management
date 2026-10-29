# SAiDL dual-shell convention; sequential algorithms avoid worker oversubscription.
param([int[]]$Seeds=@(0,1,2,3,4),[int]$Steps=20000,[int]$Workers=8)
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py=Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $py -m btms.analysis.hardness
if ($LASTEXITCODE -ne 0) { throw 'Hardness gate failed' }
& $py -m btms.analysis.evaluate controller=pid --tune
if ($LASTEXITCODE -ne 0) { throw 'PID tuning failed' }
foreach ($controller in @('null','bangbang','pid','mpc')) {
  & $py -m btms.analysis.evaluate "controller=$controller"
  if ($LASTEXITCODE -ne 0) { throw "Evaluation failed: $controller" }
  & $py -m btms.analysis.evaluate "controller=$controller" --no-shield
  if ($LASTEXITCODE -ne 0) { throw "Raw evaluation failed: $controller" }
}
foreach ($agent in @('sac','td3','ppo')) {
  foreach ($seed in $Seeds) {
    & $py -m btms.train "agent=$agent" scenario=mixed "seed=$seed" "total_steps=$Steps" "n_envs=$Workers" "log.dir=outputs/study_$Steps"
    if ($LASTEXITCODE -ne 0) { throw "Training failed: $agent seed $seed" }
  }
}
& $py -m btms.analysis.aggregate --root "outputs/study_$Steps" --out report/results
if ($LASTEXITCODE -ne 0) { throw 'Aggregation failed' }
