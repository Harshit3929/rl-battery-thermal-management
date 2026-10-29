param([Parameter(Mandatory = $true)][string]$DeckPath)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$Pns = 'http://schemas.openxmlformats.org/presentationml/2006/main'
$Ans = 'http://schemas.openxmlformats.org/drawingml/2006/main'

$replacements = @{
    1 = @{
        'Project Overview and Approach' = 'Rebuilt implementation and results'
    }
    4 = @{
        'Battery model and simulation environment' = 'Rebuilt plant and simulation environment'
        '01  Model the battery' = '01  Model the pack'
        'Use an equivalent-circuit electrical model and a lumped thermal model to simulate state of charge and temperature.' = 'Use an equivalent-circuit electrical model and four thermal nodes to simulate state of charge, heat and true spatial temperature difference.'
        '02  Check model behaviour' = '02  Check model behaviour'
        'Validate against published battery behaviour before further training. PyBaMM is an optional cross-check.' = 'A PyBaMM SPMe cross-check supports electrical lookup values. Thermal conductances remain engineering assumptions.'
        '03  Build the environment' = '03  Build the environment'
        'Wrap the model in a Gymnasium-style reset()/step() interface. Each episode applies a current or power profile.' = 'The Gymnasium environment uses independent continuous pump, fan and chiller commands with a supervisory shield.'
        '04  Prepare driving inputs' = '04  Prepare driving inputs'
        'Use NEDC, FTP-75, HWFET and US06 datasets in the planned evaluation. The reported prototype uses synthetic substitutes.' = 'Real UDDS, HWFET, US06, ECE and EUDC traces are loaded with source URLs and hashes.'
    }
    5 = @{
        'State, action and reward' = 'Rebuilt state action and reward'
        'State: what the agent observes' = 'State'
        'Battery temperatureState of charge (SoC)C-rateAmbient temperatureDriving or charging mode' = 'Four pack-node temperatures, state of charge, C-rate, ambient, operating mode and demand preview.'
        'Action: how much cooling to apply' = 'Action'
        'The reported prototype uses five cooling levels:0, 0.25, 0.5, 0.75 and 1.0.The design also includes continuous cooling effort for the planned deep-RL comparison.' = 'Independent continuous pump, fan and chiller commands coordinate coolant flow, radiator heat rejection and chiller cooling.'
        'Reward: the training objective' = 'Reward'
        'Penalise temperature-limit violations, thermal variation and cooling-energy use. Tune the weights and evaluate the resulting trade-offs.' = 'Penalise temperature-band violation, true spatial delta T, auxiliary energy and relative aging exposure.'
        'A reward penalty alone does not establish a safety guarantee.' = 'A supervisory shield provides measured intervention; reward penalties alone do not guarantee safety.'
    }
    6 = @{
        'Training and evaluation plan' = 'Training and fixed evaluation'
        'Training' = 'Training completed'
        'Start with DQN using discrete cooling actions.Compare DDPG, PPO and SAC with continuous actions through Stable-Baselines3.Use common environment settings and reward definitions for a fair comparison.' = 'PPO, SAC and TD3 trained for 20,000 environment steps each across five seeds on the mixed scenario.'
        'Evaluation against PID' = 'Fixed controller comparison'
        'Test on drive cycles held out from training.Measure time outside the temperature band and cumulative cooling energy.Inspect reward convergence and stability across seeds. Add MPC if feasible.' = 'The same eight held-out episodes compare learned policies with tuned PID, bang-bang, null and sampling MPC, with and without the shield.'
        'Metric distinction' = 'Metrics'
        'Phase II plans inter-cell temperature differences. The mid-term report gives temperature-change rate (°C/s). Report these separately when the model supports them.' = 'Report time outside band, true spatial delta T, auxiliary energy, aging exposure and shield firing rate. The temporal rate proxy is retired.'
    }
    7 = @{
        'REPORTED PROGRESS' = 'REBUILT RESULTS'
        'Prototype status and remaining work' = 'What the evidence supports'
        'Prototype described in the report' = 'Rebuilt environment'
        'The mid-term report describes a battery model, a Gym-style environment, a PID baseline and a trained tabular Q-learning agent. This is a software proof of concept.' = 'The rebuilt study uses four thermal nodes, three continuous actuators, real traces and a null-controller hardness gate.'
        'Deep-RL training pending' = 'Deep RL completed'
        'The report says the Stable-Baselines3 training script is written. Runs for DQN, DDPG, PPO and SAC remain pending, with local compute or Colab planned.' = 'PPO, SAC and TD3 trained across five seeds. The tuned PID has lower shielded mean cost than the learned policies at this budget.'
        'Official datasets still pending' = 'Safety result'
        'The reported prototype uses synthetic drive-cycle profiles. Replace them with the official datasets before the planned comparison. Reward tuning also remains open.' = 'Without the shield, learned policies violate the band for more than 41% of evaluated time. With it, violations are zero but interventions occur in about 20% of steps.'
        'Deployment study pending' = 'Deployment result'
        'The reports scope inference-latency measurement and an over-the-air retraining workflow. Vehicle deployment is not established. MPC remains optional.' = 'ONNX SAC measured 0.017 ms median on the laptop CPU; sampling MPC measured 228.949 ms. These values do not certify an automotive ECU.'
    }
    8 = @{
        'ROADMAP' = 'WORK REMAINING'
        'Next steps for the project' = 'Evidence-led next steps'
        'Official drive-cycle data' = 'Measured pack validation'
        'Replace synthetic profiles with NEDC, FTP-75, HWFET and US06 datasets. Check the model and environment before training.' = 'Validate thermal conductances and pack thermal mass against measured hardware data.'
        'Deep-RL training' = 'Longer training'
        'Run the planned algorithms using Stable-Baselines3. Use local compute or Colab, as proposed in the reports.' = 'Increase training budgets and seeds before drawing a policy-quality conclusion.'
        'Reward tuning' = 'Safety verification'
        'Adjust the safety, thermal-variation and energy weights. Evaluate whether the revised policy improves the trade-off.' = 'Test shield coverage and intervention limits on broader simulated disturbance cases.'
        'Controller comparison' = 'Broader evaluation'
        'Compare RL with PID on held-out cycles. Include an MPC baseline if time permits.' = 'Evaluate across vehicle parameters, climates and a larger held-out scenario set.'
        'SDV feasibility' = 'Target ECU'
        'Measure policy inference latency and outline the over-the-air retraining workflow for centralized or zonal compute.' = 'Benchmark the exported policy on a representative automotive compute target.'
        'Final report' = 'Result traceability'
        'Present measured results and comparison plots. Explain limitations and the work still needed for deployment.' = 'Keep every report and slide number linked to a file under report/results.'
    }
}

function Set-ShapeText([xml]$xml, [System.Xml.XmlNamespaceManager]$ns, [System.Xml.XmlElement]$shape, [string]$value) {
    $txBody = $shape.SelectSingleNode('./p:txBody', $ns)
    if ($null -eq $txBody) { return }
    $paragraphs = @($txBody.SelectNodes('./a:p', $ns))
    if ($paragraphs.Count -eq 0) { return }
    $first = $paragraphs[0]
    $firstRun = $first.SelectSingleNode('./a:r', $ns)
    $runProps = $null
    if ($null -ne $firstRun) { $runProps = $firstRun.SelectSingleNode('./a:rPr', $ns) }
    foreach ($p in $paragraphs | Select-Object -Skip 1) { [void]$txBody.RemoveChild($p) }
    foreach ($child in @($first.ChildNodes)) { if ($child.LocalName -ne 'pPr') { [void]$first.RemoveChild($child) } }
    $run = $xml.CreateElement('a', 'r', $Ans)
    if ($null -ne $runProps) { [void]$run.AppendChild($xml.ImportNode($runProps, $true)) }
    $text = $xml.CreateElement('a', 't', $Ans)
    $text.InnerText = $value
    [void]$run.AppendChild($text)
    [void]$first.AppendChild($run)
}

$zip = [System.IO.Compression.ZipFile]::Open($DeckPath, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    foreach ($slideNumber in $replacements.Keys) {
        $entryName = "ppt/slides/slide$slideNumber.xml"
        $entry = $zip.GetEntry($entryName)
        if ($null -eq $entry) { throw "Missing $entryName" }
        $reader = New-Object System.IO.StreamReader($entry.Open())
        [xml]$xml = $reader.ReadToEnd()
        $reader.Close()
        $ns = New-Object System.Xml.XmlNamespaceManager($xml.NameTable)
        $ns.AddNamespace('p', $Pns)
        $ns.AddNamespace('a', $Ans)
        $matched = 0
        foreach ($shape in @($xml.SelectNodes('//p:sp', $ns))) {
            $source = (($shape.SelectNodes('.//a:t', $ns) | ForEach-Object { $_.InnerText }) -join '')
            if ($replacements[$slideNumber].ContainsKey($source)) {
                Set-ShapeText $xml $ns $shape $replacements[$slideNumber][$source]
                $matched++
            } elseif ($slideNumber -eq 1 -and $source.StartsWith('Project Overview and Approach')) {
                Set-ShapeText $xml $ns $shape "Rebuilt implementation and results`nB.Tech Major Project, Session 2026-27"
                $matched++
            } elseif ($slideNumber -eq 6 -and $source.StartsWith('Phase II plans inter-cell temperature differences.')) {
                Set-ShapeText $xml $ns $shape 'Report time outside band, true spatial delta T, auxiliary energy, aging exposure and shield firing rate. The temporal rate proxy is retired.'
                $matched++
            }
        }
        if ($matched -ne $replacements[$slideNumber].Count) { Write-Warning "Slide $slideNumber matched $matched of $($replacements[$slideNumber].Count) expected text shapes" }
        $entry.Delete()
        $replacement = $zip.CreateEntry($entryName, [System.IO.Compression.CompressionLevel]::Optimal)
        $writer = New-Object System.IO.StreamWriter($replacement.Open(), (New-Object System.Text.UTF8Encoding($false)))
        $xml.Save($writer)
        $writer.Close()
    }
} finally { $zip.Dispose() }
