param([switch]$NoRun)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    if ($uvCommand) {
        & $uvCommand.Source venv --python 3.10 .venv
    } else {
        python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)"
        if ($LASTEXITCODE -ne 0) { throw '图形界面需要 Python 3.10–3.13；请安装对应 Python，或安装 uv 后重试。' }
        python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败' }
}
& '.\.venv\Scripts\python.exe' -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] < (3,14) else 1)"
if ($LASTEXITCODE -ne 0) { throw '现有 .venv 的 Python 版本不支持本版图形界面，请使用 Python 3.10–3.13 的环境。' }
if ($uvCommand) {
    & $uvCommand.Source pip install --python '.venv\Scripts\python.exe' -e '.[gui]'
} else {
    & '.\.venv\Scripts\python.exe' -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw '初始化 pip 失败' }
    & '.\.venv\Scripts\python.exe' -m pip install -e '.[gui]'
}
if ($LASTEXITCODE -ne 0) { throw '安装依赖失败' }
if (-not $NoRun) { & '.\.venv\Scripts\gazeboarena.exe' edit }
