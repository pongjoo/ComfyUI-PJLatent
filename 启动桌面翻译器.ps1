# PJ 桌面离线翻译器 - PowerShell 原生版
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PortableRoot = Join-Path $ScriptDir "..\..\.."
$PythonExe = Join-Path $PortableRoot "python_embeded\python.exe"

if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

# 创建主窗体
$form = New-Object System.Windows.Forms.Form
$form.Text = "PJ 本地离线智能双向翻译器 (PowerShell 原生版)"
$form.Size = New-Object System.Drawing.Size(680, 640)
$form.StartPosition = "CenterScreen"
$form.MinimumSize = New-Object System.Drawing.Size(550, 500)
$form.Font = New-Object System.Drawing.Font("Microsoft YaHei UI", 9.5)

# 顶部设置区域
$groupSetup = New-Object System.Windows.Forms.GroupBox
$groupSetup.Text = " ⚙️ 翻译设置 "
$groupSetup.Location = New-Object System.Drawing.Point(15, 10)
$groupSetup.Size = New-Object System.Drawing.Size(635, 95)
$form.Controls.Add($groupSetup)

# 模式
$lblMode = New-Object System.Windows.Forms.Label
$lblMode.Text = "翻译模式:"
$lblMode.Location = New-Object System.Drawing.Point(15, 25)
$lblMode.AutoSize = $true
$groupSetup.Controls.Add($lblMode)

$comboMode = New-Object System.Windows.Forms.ComboBox
$comboMode.DropDownStyle = [System.Windows.Forms.ComboBoxStyle]::DropDownList
$comboMode.Items.Add("Auto (智能双向检测)") | Out-Null
$comboMode.Items.Add("ZH -> EN (中译英)") | Out-Null
$comboMode.Items.Add("EN -> ZH (英译中)") | Out-Null
$comboMode.SelectedIndex = 0
$comboMode.Location = New-Object System.Drawing.Point(90, 22)
$comboMode.Size = New-Object System.Drawing.Size(200, 25)
$groupSetup.Controls.Add($comboMode)

# 前缀/后缀
$lblPrefix = New-Object System.Windows.Forms.Label
$lblPrefix.Text = "前缀词:"
$lblPrefix.Location = New-Object System.Drawing.Point(310, 25)
$lblPrefix.AutoSize = $true
$groupSetup.Controls.Add($lblPrefix)

$txtPrefix = New-Object System.Windows.Forms.TextBox
$txtPrefix.Location = New-Object System.Drawing.Point(365, 22)
$txtPrefix.Size = New-Object System.Drawing.Size(250, 25)
$groupSetup.Controls.Add($txtPrefix)

$lblSuffix = New-Object System.Windows.Forms.Label
$lblSuffix.Text = "后缀词:"
$lblSuffix.Location = New-Object System.Drawing.Point(310, 60)
$lblSuffix.AutoSize = $true
$groupSetup.Controls.Add($lblSuffix)

$txtSuffix = New-Object System.Windows.Forms.TextBox
$txtSuffix.Location = New-Object System.Drawing.Point(365, 57)
$txtSuffix.Size = New-Object System.Drawing.Size(250, 25)
$groupSetup.Controls.Add($txtSuffix)

# 输入区域
$lblInput = New-Object System.Windows.Forms.Label
$lblInput.Text = "📥 输入文本 (中文或英文):"
$lblInput.Location = New-Object System.Drawing.Point(15, 115)
$lblInput.AutoSize = $true
$form.Controls.Add($lblInput)

$txtInput = New-Object System.Windows.Forms.TextBox
$txtInput.Multiline = $true
$txtInput.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$txtInput.Location = New-Object System.Drawing.Point(15, 140)
$txtInput.Size = New-Object System.Drawing.Size(635, 150)
$txtInput.Font = New-Object System.Drawing.Font("Consolas", 10.5)
$form.Controls.Add($txtInput)

# 按钮区域
$btnTranslate = New-Object System.Windows.Forms.Button
$btnTranslate.Text = "⚡ 开始离线翻译"
$btnTranslate.Location = New-Object System.Drawing.Point(15, 300)
$btnTranslate.Size = New-Object System.Drawing.Size(515, 35)
$btnTranslate.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 215)
$btnTranslate.ForeColor = [System.Drawing.Color]::White
$btnTranslate.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$form.Controls.Add($btnTranslate)

$btnClear = New-Object System.Windows.Forms.Button
$btnClear.Text = "清空"
$btnClear.Location = New-Object System.Drawing.Point(540, 300)
$btnClear.Size = New-Object System.Drawing.Size(110, 35)
$form.Controls.Add($btnClear)

# 输出区域
$lblOutput = New-Object System.Windows.Forms.Label
$lblOutput.Text = "📤 翻译结果:"
$lblOutput.Location = New-Object System.Drawing.Point(15, 345)
$lblOutput.AutoSize = $true
$form.Controls.Add($lblOutput)

$txtOutput = New-Object System.Windows.Forms.TextBox
$txtOutput.Multiline = $true
$txtOutput.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
$txtOutput.Location = New-Object System.Drawing.Point(15, 370)
$txtOutput.Size = New-Object System.Drawing.Size(635, 150)
$txtOutput.Font = New-Object System.Drawing.Font("Consolas", 10.5)
$form.Controls.Add($txtOutput)

# 底部
$btnCopy = New-Object System.Windows.Forms.Button
$btnCopy.Text = "📋 复制结果"
$btnCopy.Location = New-Object System.Drawing.Point(540, 530)
$btnCopy.Size = New-Object System.Drawing.Size(110, 30)
$form.Controls.Add($btnCopy)

$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "就绪 - 原生 PowerShell 极速架构 (100% 纯离线)"
$statusLabel.Location = New-Object System.Drawing.Point(15, 535)
$statusLabel.AutoSize = $true
$statusLabel.ForeColor = [System.Drawing.Color]::Gray
$form.Controls.Add($statusLabel)

# 事件响应
$btnClear.Add_Click({
    $txtInput.Text = ""
})

$btnCopy.Add_Click({
    if ($txtOutput.Text.Trim() -ne "") {
        [System.Windows.Forms.Clipboard]::SetText($txtOutput.Text)
        $statusLabel.Text = "已成功复制到剪贴板！"
        $statusLabel.ForeColor = [System.Drawing.Color]::Green
    }
})

$btnTranslate.Add_Click({
    $text = $txtInput.Text.Trim()
    if ($text -eq "") {
        $statusLabel.Text = "提示: 请先输入需要翻译的文本"
        $statusLabel.ForeColor = [System.Drawing.Color]::Red
        return
    }

    $btnTranslate.Enabled = $false
    $statusLabel.Text = "⌛ 正在离线翻译中，请稍候..."
    $statusLabel.ForeColor = [System.Drawing.Color]::Blue
    $form.Refresh()

    $mode = $comboMode.SelectedItem.ToString()
    $prefix = $txtPrefix.Text
    $suffix = $txtSuffix.Text
    $cliScript = Join-Path $ScriptDir "pj_cli_translate.py"

    try {
        $pinfo = New-Object System.Diagnostics.ProcessStartInfo
        $pinfo.FileName = $PythonExe
        $pinfo.Arguments = "`"$cliScript`" --text `"$($text.Replace('"', '\"'))`" --mode `"$mode`" --prefix `"$prefix`" --suffix `"$suffix`""
        $pinfo.RedirectStandardOutput = $true
        $pinfo.RedirectStandardError = $true
        $pinfo.UseShellExecute = $false
        $pinfo.CreateNoWindow = $true
        $pinfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8

        $p = [System.Diagnostics.Process]::Start($pinfo)
        $stdout = $p.StandardOutput.ReadToEnd()
        $stderr = $p.StandardError.ReadToEnd()
        $p.WaitForExit()

        if ($stdout -ne "") {
            try {
                $jsonObj = $stdout | ConvertFrom-Json
                if ($jsonObj.result) {
                    $txtOutput.Text = $jsonObj.result
                    $statusLabel.Text = "翻译完成！"
                    $statusLabel.ForeColor = [System.Drawing.Color]::Green
                } elseif ($jsonObj.error) {
                    $txtOutput.Text = "错误: " + $jsonObj.error
                    $statusLabel.Text = "翻译失败"
                    $statusLabel.ForeColor = [System.Drawing.Color]::Red
                }
            } catch {
                $txtOutput.Text = $stdout
                $statusLabel.Text = "完成"
                $statusLabel.ForeColor = [System.Drawing.Color]::Green
            }
        } else {
            $txtOutput.Text = "报错信息:`r`n" + $stderr
            $statusLabel.Text = "执行出错"
            $statusLabel.ForeColor = [System.Drawing.Color]::Red
        }
    } catch {
        $txtOutput.Text = "运行捕获错误: " + $_.Exception.Message
        $statusLabel.Text = "出现异常"
        $statusLabel.ForeColor = [System.Drawing.Color]::Red
    } finally {
        $btnTranslate.Enabled = $true
    }
})

[void]$form.ShowDialog()
