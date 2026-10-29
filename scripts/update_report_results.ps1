param(
    [Parameter(Mandatory = $true)][string]$Phase3Path,
    [Parameter(Mandatory = $true)][string]$MidtermPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$WordNs = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

function Get-ParagraphText([System.Xml.XmlElement]$paragraph, [System.Xml.XmlNamespaceManager]$ns) {
    return (($paragraph.SelectNodes('.//w:t', $ns) | ForEach-Object { $_.InnerText }) -join '')
}

function New-Paragraph([xml]$doc, [System.Xml.XmlNamespaceManager]$ns, [System.Xml.XmlElement]$template, [string]$text, [bool]$bold = $false) {
    $p = $doc.CreateElement('w', 'p', $WordNs)
    $pPr = $template.SelectSingleNode('./w:pPr', $ns)
    if ($null -ne $pPr) { [void]$p.AppendChild($doc.ImportNode($pPr, $true)) }
    $r = $doc.CreateElement('w', 'r', $WordNs)
    if ($bold) {
        $rPr = $doc.CreateElement('w', 'rPr', $WordNs)
        [void]$rPr.AppendChild($doc.CreateElement('w', 'b', $WordNs))
        [void]$r.AppendChild($rPr)
    }
    $t = $doc.CreateElement('w', 't', $WordNs)
    if ($text.StartsWith(' ') -or $text.EndsWith(' ')) { $t.SetAttribute('xml:space', 'http://www.w3.org/XML/1998/namespace', 'preserve') }
    $t.InnerText = $text
    [void]$r.AppendChild($t)
    [void]$p.AppendChild($r)
    return ,$p
}

function New-Cell([xml]$doc, [System.Xml.XmlNamespaceManager]$ns, [System.Xml.XmlElement]$bodyTemplate, [string]$text, [bool]$header) {
    $tc = $doc.CreateElement('w', 'tc', $WordNs)
    $tcPr = $doc.CreateElement('w', 'tcPr', $WordNs)
    $tcW = $doc.CreateElement('w', 'tcW', $WordNs)
    [void]$tcW.SetAttribute('w', $WordNs, '0')
    [void]$tcW.SetAttribute('type', $WordNs, 'auto')
    [void]$tcPr.AppendChild($tcW)
    if ($header) {
        $shd = $doc.CreateElement('w', 'shd', $WordNs)
        [void]$shd.SetAttribute('fill', $WordNs, '1F4E78')
        [void]$shd.SetAttribute('val', $WordNs, 'clear')
        [void]$tcPr.AppendChild($shd)
    }
    [void]$tc.AppendChild($tcPr)
    [void]$tc.AppendChild((New-Paragraph $doc $ns $bodyTemplate $text $header))
    return ,$tc
}

function New-Table([xml]$doc, [System.Xml.XmlNamespaceManager]$ns, [System.Xml.XmlElement]$bodyTemplate, [string[][]]$rows) {
    $tbl = $doc.CreateElement('w', 'tbl', $WordNs)
    $tblPr = $doc.CreateElement('w', 'tblPr', $WordNs)
    $tblW = $doc.CreateElement('w', 'tblW', $WordNs)
    [void]$tblW.SetAttribute('w', $WordNs, '0')
    [void]$tblW.SetAttribute('type', $WordNs, 'auto')
    [void]$tblPr.AppendChild($tblW)
    $borders = $doc.CreateElement('w', 'tblBorders', $WordNs)
    foreach ($side in @('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) {
        $border = $doc.CreateElement('w', $side, $WordNs)
        [void]$border.SetAttribute('val', $WordNs, 'single')
        [void]$border.SetAttribute('sz', $WordNs, '4')
        [void]$border.SetAttribute('space', $WordNs, '0')
        [void]$border.SetAttribute('color', $WordNs, 'D9D9D9')
        [void]$borders.AppendChild($border)
    }
    [void]$tblPr.AppendChild($borders)
    [void]$tbl.AppendChild($tblPr)
    $grid = $doc.CreateElement('w', 'tblGrid', $WordNs)
    for ($i = 0; $i -lt $rows[0].Count; $i++) {
        $gridCol = $doc.CreateElement('w', 'gridCol', $WordNs)
        [void]$gridCol.SetAttribute('w', $WordNs, [string][int](9000 / $rows[0].Count))
        [void]$grid.AppendChild($gridCol)
    }
    [void]$tbl.AppendChild($grid)
    for ($r = 0; $r -lt $rows.Count; $r++) {
        $tr = $doc.CreateElement('w', 'tr', $WordNs)
        foreach ($cellText in $rows[$r]) { $cell = New-Cell $doc $ns $bodyTemplate $cellText ($r -eq 0); [void]$tr.AppendChild([System.Xml.XmlNode]$cell) }
        [void]$tbl.AppendChild($tr)
    }
    return ,$tbl
}

function Replace-Section([string]$path, [string]$startText, [string]$endText, [object[]]$newElements) {
    $zip = [System.IO.Compression.ZipFile]::Open($path, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        $entry = $zip.GetEntry('word/document.xml')
        if ($null -eq $entry) { throw "word/document.xml not found in $path" }
        $reader = New-Object System.IO.StreamReader($entry.Open())
        [xml]$doc = $reader.ReadToEnd()
        $reader.Close()
        $ns = New-Object System.Xml.XmlNamespaceManager($doc.NameTable)
        $ns.AddNamespace('w', $WordNs)
        $paragraphs = @($doc.SelectNodes('//w:body/w:p', $ns))
        $start = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Trim() -eq $startText } | Select-Object -First 1
        $end = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Trim() -eq $endText } | Select-Object -First 1
        if ($null -eq $start -or $null -eq $end) { throw "Could not find section boundary '$startText' or '$endText' in $path" }
        $body = $doc.SelectSingleNode('//w:body', $ns)
        $bodyTemplate = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Length -gt 120 } | Select-Object -First 1
        $headingTemplate = $start
        $inRange = $false
        $remove = @()
        foreach ($child in @($body.ChildNodes)) {
            if ($child -eq $start) { $inRange = $true; $remove += $child; continue }
            if ($child -eq $end) { break }
            if ($inRange) { $remove += $child }
        }
        foreach ($child in $remove) { [void]$body.RemoveChild($child) }
        $anchor = $end
        for ($i = $newElements.Count - 1; $i -ge 0; $i--) { [void]$body.InsertBefore($doc.ImportNode($newElements[$i], $true), $anchor) }
        $entry.Delete()
        $replacement = $zip.CreateEntry('word/document.xml', [System.IO.Compression.CompressionLevel]::Optimal)
        $writer = New-Object System.IO.StreamWriter($replacement.Open(), (New-Object System.Text.UTF8Encoding($false)))
        $doc.Save($writer)
        $writer.Close()
    } finally { $zip.Dispose() }
}

function New-Phase3Elements([string]$path) {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($path)
    try {
        $entry = $zip.GetEntry('word/document.xml'); $reader = New-Object System.IO.StreamReader($entry.Open()); [xml]$doc = $reader.ReadToEnd(); $reader.Close()
    } finally { $zip.Dispose() }
    $ns = New-Object System.Xml.XmlNamespaceManager($doc.NameTable); $ns.AddNamespace('w', $WordNs)
    $paragraphs = @($doc.SelectNodes('//w:body/w:p', $ns)); $bodyTemplate = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Length -gt 120 } | Select-Object -First 1
    $heading = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Trim() -eq '3. TESTING & VALIDATION' } | Select-Object -First 1
    $subheading = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Trim() -eq '3.1 Unit-Level Checks' } | Select-Object -First 1
    $items = New-Object System.Collections.Generic.List[object]
    $items.Add((New-Paragraph $doc $ns $heading '3. TESTING AND VALIDATION' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'This section supersedes the earlier synthetic-cycle and tabular-Q-learning validation. The rebuilt study used real UDDS, HWFET, US06, ECE and EUDC source traces, a four-node pack model, continuous pump, fan and chiller actions, and a fixed held-out evaluation set. Results are traceable to report/results.' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '3.1 Plant and input checks' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'Five physics and normalizer tests passed. The null-controller hardness gate passed: without cooling, mild stays within the band, while hot violates the band for 1,472 of 1,800 s and fast charge for 1,181 of 1,350 s. Full cooling held the hot case below 45 C and the fast-charge case below 45 C. The energy-residual records in the gate are near numerical precision.' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'Four real drive-cycle files loaded with recorded source URLs and hashes. The unadjusted road-load model reports 13.26, 13.30, 18.74 and 13.99 kWh per 100 km for UDDS, HWFET, US06 and NEDC respectively. These values are retained as calculated rather than rescaled to a generic target. A PyBaMM SPMe cross-check at four state-of-charge points supports the electrical lookup values, while the pack conductances and hardware mass remain engineering assumptions rather than experimental validation.' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '3.2 Training and evaluation protocol' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'PPO, SAC and TD3 each trained for 20,000 environment steps across five seeds on the mixed scenario. The learned policies and four deterministic baselines were replayed on the same eight held-out episodes. Shielded and unshielded evaluations are reported separately. PID tuning used a disjoint tuning split and the same integrated cost as the learned policies; the selected setting was 39 C with Kp 0.6, Ki 0 and Kd 0.' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '3.3 Safety validation' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'The supervisory shield produced zero recorded safety-band violation for every evaluated controller. That result is conditional on intervention: learned policies fired the shield for 19.63% to 22.70% of evaluation steps. Without the shield, PPO, SAC and TD3 violated the band for 42.28%, 41.15% and 42.08% of evaluated time respectively. The shield therefore provides supervisory safety in this model; it does not demonstrate that the learned policies are independently safe.' $false))
    $items.Add((New-Paragraph $doc $ns $heading '4. PERFORMANCE ANALYSIS' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'The previous 95% cooling-energy claim and the max |dT/dt| temperature-gradient proxy are retired. The updated metric is the true maximum spatial temperature difference across the four thermal nodes. The primary comparison uses the shielded fixed evaluation set because it permits like-for-like zero recorded violations while exposing intervention frequency.' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '4.1 Training results' $false))
    $items.Add((New-Table $doc $ns $bodyTemplate @(
        @('Algorithm', 'Seeds', 'Final mean reward', 'Final standard deviation'),
        @('PPO', '5', '-1762.07', '71.77'),
        @('SAC', '5', '-1983.91', '11.69'),
        @('TD3', '5', '-1934.04', '47.95')
    )))
    $items.Add((New-Paragraph $doc $ns $subheading '4.2 Shielded controller comparison' $false))
    $items.Add((New-Table $doc $ns $bodyTemplate @(
        @('Controller', 'Seeds', 'Cost mean', 'Aux Wh mean', 'Shield firing %', 'Spatial delta C'),
        @('PID tuned', '1', '1737.38', '482.31', '1.23', '1.79'),
        @('Bang-bang', '1', '1983.07', '626.79', '1.23', '2.26'),
        @('MPC sampling', '1', '1618.36', '445.26', '14.31', '1.31'),
        @('PPO', '5', '1841.61', '474.76', '22.70', '2.15'),
        @('SAC', '5', '1768.50', '490.39', '19.63', '1.91'),
        @('TD3', '5', '1750.04', '483.99', '21.85', '1.83')
    )))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'All shielded rows recorded 0.0% violation on the eight-episode evaluation set. The tuned PID has the lowest shielded mean cost among the learned policies. Sampling MPC has lower mean cost in this evaluation but needs substantially more computation and calls the shield more often. These outcomes do not establish an RL advantage over the tuned PID at the present training budget.' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '4.3 Deployment benchmark' $false))
    $items.Add((New-Table $doc $ns $bodyTemplate @(
        @('Runtime', 'Median ms', 'p95 ms', '10 Hz headroom', 'Footprint KB'),
        @('PyTorch SAC', '0.0920', '0.1220', '526.7x', 'not recorded'),
        @('ONNX SAC', '0.0170', '0.0182', '3901.4x', '24.94'),
        @('INT8 ONNX SAC', '0.0217', '0.0247', '3046.6x', '16.04'),
        @('Sampling MPC', '228.9490', '262.3432', '0.35x', 'not applicable')
    )))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'The benchmark ran on a 13th Gen Intel Core i5-13420H CPU with a 100 ms reference period. It establishes laptop CPU headroom only and cannot certify an automotive ECU. ONNX and INT8 action differences from the PyTorch policy were checked, but quantized quality was not used to claim superior control performance.' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '4.4 Interpretation and limitations' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'The rebuild closes the original implementation gaps: it uses a multi-node spatial model, three independently commanded actuators, real drive-cycle traces and five learned-policy seeds. It also changes the conclusion. The current learned policies rely materially on the shield and do not outperform the fairly tuned PID on shielded mean cost. Future work should extend training, validate thermal parameters against measured pack data, and evaluate policies on a target ECU before making a deployment claim.' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'Evidence files: report/results/hardness_gate.json, cycle_report.json, parameter_reference.json, pid_tuning.json, policy_evaluation_summary.csv, summary.csv, deployment_benchmark_sac_seed0.json.' $false))
    return $items.ToArray()
}

function New-MidtermElements([string]$path) {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($path)
    try { $entry = $zip.GetEntry('word/document.xml'); $reader = New-Object System.IO.StreamReader($entry.Open()); [xml]$doc = $reader.ReadToEnd(); $reader.Close() } finally { $zip.Dispose() }
    $ns = New-Object System.Xml.XmlNamespaceManager($doc.NameTable); $ns.AddNamespace('w', $WordNs)
    $paragraphs = @($doc.SelectNodes('//w:body/w:p', $ns)); $bodyTemplate = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Length -gt 120 } | Select-Object -First 1
    $heading = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Trim() -eq '1. DESIGN REVIEW' } | Select-Object -First 1
    $subheading = $paragraphs | Where-Object { (Get-ParagraphText $_ $ns).Trim() -eq '2.1 What Is Working' } | Select-Object -First 1
    $items = New-Object System.Collections.Generic.List[object]
    $items.Add((New-Paragraph $doc $ns $heading '1. DESIGN REVIEW' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'The rebuilt implementation deliberately corrects material deviations in the earlier prototype. The previous statement that no deviations existed is withdrawn. The original implementation used one thermal node, a scalar cooling command, synthetic profiles and a temporal max |dT/dt| proxy. Those choices could not implement the promised inter-cell gradient or multi-actuator coordination.' $false))
    $items.Add((New-Table $doc $ns $bodyTemplate @(
        @('Design element', 'Rebuilt implementation', 'Review outcome'),
        @('Thermal state', 'Four nodes with coolant warming and spatial delta T', 'Corrects the one-node limitation'),
        @('Action space', 'Continuous pump, fan and chiller commands', 'Implements multi-actuator coordination'),
        @('Drive inputs', 'Real UDDS, HWFET, US06, ECE and EUDC traces with hashes', 'Synthetic inputs retired'),
        @('Reward metric', 'True spatial delta T across nodes', 'Temporal rate proxy retired'),
        @('Algorithms', 'PPO, SAC and TD3, five seeds each', 'Deep RL executed; DQN not included'),
        @('Baselines', 'Tuned PID, bang-bang, null and sampling MPC', 'Fair PID tuning and MPC comparison added'),
        @('Safety', 'Supervisory shield measured separately', 'Zero violation is conditional on intervention')
    )))
    $items.Add((New-Paragraph $doc $ns $heading '2. PROTOTYPE AND IMPLEMENTATION PROGRESS' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '2.1 What is working' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'The working pipeline includes longitudinal road load, a first-order electrical model, four thermal nodes, independent cooling actuators, Gymnasium environment, fixed evaluation episodes, controller baselines, PPO/SAC/TD3 training and an ONNX/INT8 laptop deployment benchmark. The null-controller hardness gate demonstrates that doing nothing is unsafe in hot and fast-charge scenarios.' $false))
    $items.Add((New-Paragraph $doc $ns $subheading '2.2 What remains' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'Measured pack validation remains open: conductances and pack hardware mass are engineering assumptions. The 20,000-step policies need longer and broader training before any superiority claim. The deployment result is a laptop CPU benchmark, not a vehicle ECU certification. The safety shield has not been formally verified beyond the simulated cases.' $false))
    $items.Add((New-Paragraph $doc $ns $heading '3. EXPERIMENTAL RESULTS' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'The current results replace the previous synthetic-cycle 95% energy-saving headline. On the eight fixed held-out episodes with the shield enabled, all controllers recorded zero band violation. PPO, SAC and TD3 required the shield for 22.70%, 19.63% and 21.85% of steps respectively. Their mean costs were 1841.61, 1768.50 and 1750.04, versus 1737.38 for the fairly tuned PID. The study therefore does not claim that RL has beaten PID at the present budget.' $false))
    $items.Add((New-Paragraph $doc $ns $bodyTemplate 'Unshielded PPO, SAC and TD3 each violated the thermal band for more than 41% of evaluated time. This result demonstrates why a soft reward penalty cannot serve as a safety guarantee. The correct presentation is a supervised controller study with measured intervention frequency, rather than an independently safe RL result.' $false))
    $items.Add((New-Table $doc $ns $bodyTemplate @(
        @('Metric', 'Verified result', 'Evidence file'),
        @('Hardness gate', 'Null cooling violates hot and fast-charge band', 'hardness_gate.json'),
        @('PID tuning', '39 C, Kp 0.6, Ki 0, Kd 0', 'pid_tuning.json'),
        @('Shielded RL cost', 'PPO 1841.61; SAC 1768.50; TD3 1750.04', 'policy_evaluation_summary.csv'),
        @('Unshielded RL violation', 'PPO 42.28%; SAC 41.15%; TD3 42.08%', 'policy_evaluation_summary.csv'),
        @('ONNX latency', '0.0170 ms median on laptop CPU', 'deployment_benchmark_sac_seed0.json')
    )))
    return $items.ToArray()
}

Replace-Section -path $Phase3Path -startText '3. TESTING & VALIDATION' -endText '5. ACHIEVEMENT OF MILESTONES' -newElements (New-Phase3Elements $Phase3Path)
Replace-Section -path $MidtermPath -startText '1. DESIGN REVIEW' -endText '4. MID-TERM PRESENTATION OUTLINE' -newElements (New-MidtermElements $MidtermPath)
