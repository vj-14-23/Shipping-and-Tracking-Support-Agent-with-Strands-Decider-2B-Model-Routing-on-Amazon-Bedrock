# AWS User Group Madurai: Strands Decider hackathon kit installer (Windows).
#
# In Kiro: open an EMPTY folder, open the terminal (Ctrl+`), then run:
#   irm __BASE__/install.ps1 | iex
# From GitHub (until the kit is hosted):
#   irm https://raw.githubusercontent.com/Vivek0712/decider-hackathon-kit/main/install/install.ps1 | iex
# (private repo: set $env:GITHUB_TOKEN = (gh auth token) first)
#
# It asks before installing anything. uv, Python 3.12, the kit and its packages go into your user
# folder (no admin rights); git and the GitHub CLI come from winget or your user folder.
# Unattended: $env:KIT_YES = "1". Another host: $env:KIT_BASE_URL = "..."
$ErrorActionPreference = "Stop"
# Where the kit comes from: a hosted release (./kit release fills this in), else GitHub's archive
$ZipDefault = "https://codeload.github.com/Vivek0712/decider-hackathon-kit/zip/refs/heads/main"
$ZipUrl = if ($env:KIT_ZIP) { $env:KIT_ZIP } elseif ($env:KIT_BASE_URL) { "$($env:KIT_BASE_URL)/decider-hackathon-kit.zip" } else { $ZipDefault }
$Headers = @{}; if ($env:GITHUB_TOKEN) { $Headers["Authorization"] = "Bearer $($env:GITHUB_TOKEN)" }
function Ask($q) {
  if ($env:KIT_YES) { return $true }
  $a = Read-Host "$q [Y/n]"
  return ($a -eq "" -or $a -match '^(y|yes)$')
}

Write-Host ""
Write-Host "Strands Decider hackathon kit  (AWS User Group Madurai)"
Write-Host "Installing into: $(Get-Location)"
Write-Host ""

# 1. An empty folder (Kiro must open the kit's own folder to find its /hackathon skill)
if (Test-Path "scripts\kit.py") {
  Write-Host "The kit is already here: updating its Python environment."
} elseif (Get-ChildItem -Force | Where-Object { -not $_.Name.StartsWith(".") }) {
  Write-Host "This folder is not empty. In Kiro: File > Open Folder, make a new empty folder, open it, and run this again."
  exit 1
}

# 2. uv: installs Python and the kit's packages, in your user folder
$uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $uv -and (Test-Path "$HOME\.local\bin\uv.exe")) { $uv = "$HOME\.local\bin\uv.exe" }
if (-not $uv) {
  Write-Host "Needed: uv (installs Python 3.12 and the kit's packages; about 30 MB, into your user folder, no admin)."
  if (-not (Ask "Install uv now?")) { Write-Host "Stopped. Nothing was installed."; exit 1 }
  $env:UV_NO_MODIFY_PATH = "1"
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression | Out-Null
  $uv = "$HOME\.local\bin\uv.exe"
}
Write-Host "OK  $(& $uv --version)"

# 3. The kit
if (-not (Test-Path "scripts\kit.py")) {
  Write-Host "Downloading the kit ..."
  $zip = Join-Path $env:TEMP "decider-hackathon-kit.zip"
  $tmp = Join-Path $env:TEMP ("decider-kit-" + [guid]::NewGuid())
  Invoke-WebRequest $ZipUrl -OutFile $zip -UseBasicParsing -Headers $Headers
  Expand-Archive $zip -DestinationPath $tmp -Force
  $top = Get-ChildItem $tmp | Select-Object -First 1
  Get-ChildItem -Force $top.FullName | Move-Item -Destination (Get-Location)
  Remove-Item $zip, $tmp -Recurse -Force
  Write-Host "OK  kit $(Get-Content VERSION -ErrorAction SilentlyContinue)"
}

# 4. Python 3.12 and the kit's packages (about 2 min)
& $uv python install 3.12 | Out-Null
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $uv venv -q --python 3.12 .venv }
$env:PATH = "$HOME\.local\bin;$env:PATH"
.\kit.cmd venv
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# 5. Tools for publishing and deploying: git, GitHub CLI, Node (asks first)
.\kit.cmd tools install base

Write-Host ""
Write-Host "Done. Now, in the Kiro chat, type:   /hackathon"
Write-Host "Kiro will ask which path you want (AWS, fully local, or the user group cloud), set it up, and build your agent with you."
