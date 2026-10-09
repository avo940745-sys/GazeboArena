param([switch]$NoRun)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败' }
}
& '.\.venv\Scripts\python.exe' -m pip install -e '.[gui]'
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
if (-not $NoRun) { & '.\.venv\Scripts\gazeboarena.exe' edit }
