<#
.SYNOPSIS
    BuddyKeyManager 一键发布脚本：在本机用 GitHub PAT 新建仓库并推送代码。

.DESCRIPTION
    1. 从系统环境变量 workbuddy-github 读取 GitHub PAT（绝不要求你手动输入令牌）。
    2. 交互询问：GitHub 用户名、仓库名、可见性、描述。
    3. 调用 GitHub API 创建仓库。
    4. git 初始化并提交全部文件（.env / data/ 已被 .gitignore 排除，不会上传）。
    5. 推送至 origin/main。

.NOTES
    运行方式（在 PowerShell 中，项目根目录下执行）：
        .\publish.ps1
    前置要求：已安装 git 且 git 在 PATH 中；系统已设置环境变量 workbuddy-github。
#>

$ErrorActionPreference = 'Stop'

# ---------- 1. 读取 PAT ----------
$pat = [Environment]::GetEnvironmentVariable('workbuddy-github', 'User')  # 先查用户级
if ([string]::IsNullOrWhiteSpace($pat)) {
    $pat = [Environment]::GetEnvironmentVariable('workbuddy-github', 'Machine')  # 再查系统级
}
if ([string]::IsNullOrWhiteSpace($pat)) {
    $pat = $env:workbuddy-github  # 当前进程级兜底
}
if ([string]::IsNullOrWhiteSpace($pat)) {
    Write-Error "未找到 GitHub PAT。请先在系统环境变量中设置名称为 workbuddy-github 的变量，再运行本脚本。"
    exit 1
}

# ---------- 2. 仓库信息（交互输入） ----------
$projectRoot = $PSScriptRoot
$defaultRepo = (Split-Path $projectRoot -Leaf)
$githubUser  = Read-Host -Prompt "GitHub 用户名"
$repoName    = Read-Host -Prompt "仓库名（回车用 '$defaultRepo'）"
if ([string]::IsNullOrWhiteSpace($repoName)) { $repoName = $defaultRepo }

$vis = Read-Host -Prompt "仓库可见性 [private/public]（默认 private）"
$private = -not ($vis -eq 'public')
$desc    = Read-Host -Prompt "仓库描述（可留空）"

# ---------- 3. 通过 GitHub API 创建仓库 ----------
$apiUrl = 'https://api.github.com/user/repos'
$headers = @{
    Authorization = "Bearer $pat"
    Accept        = 'application/vnd.github+json'
}
$body = @{
    name        = $repoName
    private     = $private
    description = $desc
    auto_init   = $false
} | ConvertTo-Json

Write-Host "正在创建 GitHub 仓库 $githubUser/$repoName ..." -ForegroundColor Cyan
try {
    $resp = Invoke-RestMethod -Uri $apiUrl -Method Post -Headers $headers -Body $body `
        -ContentType 'application/json' -ErrorAction Stop
    $remoteUrl = $resp.clone_url
    Write-Host "仓库已创建：$remoteUrl" -ForegroundColor Green
}
catch {
    # 409 通常表示已存在同名仓库，允许继续
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode.Value__ -eq 409) {
        Write-Host "同名仓库已存在，尝试直接推送到已有仓库。" -ForegroundColor Yellow
        $remoteUrl = "https://github.com/$githubUser/$repoName.git"
    }
    else {
        Write-Error "创建仓库失败：$($_.Exception.Message)"
        exit 1
    }
}

# ---------- 4. git 初始化与提交 ----------
Push-Location $projectRoot
try {
    if (-not (Test-Path .git)) {
        git init | Out-Null
    }
    git config user.email "bot@buddykey.local"
    git config user.name  $githubUser

    # 确保不提交敏感文件（.gitignore 已排除 .env / data/ 等）
    git add -A
    $status = git status --porcelain
    if ([string]::IsNullOrWhiteSpace($status)) {
        Write-Host "没有需要提交的改动。" -ForegroundColor Yellow
    }
    else {
        git commit -m "chore: initial commit (BuddyKeyManager scaffold)" | Out-Null
        Write-Host "已提交本地改动。" -ForegroundColor Green
    }

    # ---------- 5. 设置远程并推送 ----------
    $existing = git remote get-url origin 2>$null
    if ($existing) {
        git remote set-url origin $remoteUrl
    }
    else {
        git remote add origin $remoteUrl
    }

    # 统一使用 main 分支
    $branch = git rev-parse --abbrev-ref HEAD 2>$null
    if ($branch -ne 'main') {
        git branch -M main
    }

    # 用 PAT 作为凭据推送（仅本次，不写入文件）
    $authUrl = "https://$githubUser`:$pat@github.com/$githubUser/$repoName.git"
    git push -u $authUrl main 2>&1 | ForEach-Object { Write-Host $_ }
    Write-Host "✅ 已推送至 https://github.com/$githubUser/$repoName" -ForegroundColor Green
}
finally {
    Pop-Location
}
