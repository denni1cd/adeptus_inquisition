<#
.SYNOPSIS
Runs the full pytest suite from a disposable checkout of an exact local Git commit.

.DESCRIPTION
Uses fixed pytest options against the checkout root. Caller-supplied pytest arguments are not accepted.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $SourceRepository,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$')]
    [string] $Commit,

    [Parameter(Mandatory = $true)]
    [string] $PythonExecutable,

    [Parameter(Mandatory = $true)]
    [string] $EvidenceDirectory
)

$ErrorActionPreference = 'Stop'
$nativeCommandPreference = Get-Variable -Name 'PSNativeCommandUseErrorActionPreference' -ErrorAction SilentlyContinue
$hadNativeCommandPreference = $null -ne $nativeCommandPreference
if ($hadNativeCommandPreference) {
    $savedNativeCommandPreference = $nativeCommandPreference.Value
    $PSNativeCommandUseErrorActionPreference = $false
}

function Get-NormalizedPath {
    param([Parameter(Mandatory = $true)][string] $Path)

    $full = [System.IO.Path]::GetFullPath($Path)
    $root = [System.IO.Path]::GetPathRoot($full)
    $directorySeparator = [string][System.IO.Path]::DirectorySeparatorChar
    $alternateSeparator = [string][System.IO.Path]::AltDirectorySeparatorChar
    while ($full.Length -gt $root.Length -and
        ($full.EndsWith($directorySeparator) -or
         $full.EndsWith($alternateSeparator))) {
        $full = $full.Substring(0, $full.Length - 1)
    }
    return $full
}

function Resolve-FuturePath {
    param([Parameter(Mandatory = $true)][string] $Path)

    $pending = New-Object 'System.Collections.Generic.List[string]'
    $cursor = Get-NormalizedPath -Path $Path
    while (-not (Test-Path -LiteralPath $cursor)) {
        $leaf = [System.IO.Path]::GetFileName($cursor)
        if ([string]::IsNullOrWhiteSpace($leaf)) {
            throw "Cannot resolve path because no existing parent was found: $Path"
        }
        $pending.Insert(0, $leaf)
        $parent = [System.IO.Path]::GetDirectoryName($cursor)
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $cursor) {
            throw "Cannot resolve path because no existing parent was found: $Path"
        }
        $cursor = $parent
    }

    $resolved = (Resolve-Path -LiteralPath $cursor).Path
    foreach ($part in $pending) {
        $resolved = Join-Path -Path $resolved -ChildPath $part
    }
    return Get-NormalizedPath -Path $resolved
}

function Test-PathEqual {
    param([string] $Left, [string] $Right)
    return [string]::Equals(
        (Get-NormalizedPath -Path $Left),
        (Get-NormalizedPath -Path $Right),
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Test-PathInside {
    param([string] $Candidate, [string] $Parent)

    $candidatePath = Get-NormalizedPath -Path $Candidate
    $parentPath = Get-NormalizedPath -Path $Parent
    $separator = [System.IO.Path]::DirectorySeparatorChar
    if (-not $parentPath.EndsWith($separator)) {
        $parentPath += $separator
    }
    return $candidatePath.StartsWith($parentPath, [System.StringComparison]::OrdinalIgnoreCase)
}

function Resolve-NativeExecutable {
    param([Parameter(Mandatory = $true)][string] $Name)

    if (Test-Path -LiteralPath $Name -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Name).Path
    }

    $applicationMatches = @(Get-Command -Name $Name -CommandType Application -ErrorAction Stop)
    foreach ($match in $applicationMatches) {
        $candidate = [string]$match.Path
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            $candidate = [string]$match.Source
        }
        if (-not [string]::IsNullOrWhiteSpace($candidate) -and
            (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "No executable file found for command: $Name"
}

function Invoke-GitCapture {
    param(
        [Parameter(Mandatory = $true)][string] $GitExecutable,
        [Parameter(Mandatory = $true)][string] $Repository,
        [Parameter(Mandatory = $true)][string[]] $GitArgs
    )

    $allArgs = @('-C', $Repository) + $GitArgs
    $output = @(& $GitExecutable @allArgs 2>&1)
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        $detail = ($output | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
        throw "git $($GitArgs -join ' ') failed with exit code $code. $detail"
    }
    return $output
}

function Get-FileSha256OrMissing {
    param([Parameter(Mandatory = $true)][string] $Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return 'MISSING'
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-SourceSnapshot {
    param(
        [Parameter(Mandatory = $true)][string] $Repository,
        [Parameter(Mandatory = $true)][string] $GitExecutable
    )

    $rootOutput = @(Invoke-GitCapture -GitExecutable $GitExecutable -Repository $Repository -GitArgs @('rev-parse', '--show-toplevel'))
    if ($rootOutput.Count -lt 1 -or -not (Test-PathEqual -Left ([string]$rootOutput[0]) -Right $Repository)) {
        throw "Source path is not the root of a Git repository: $Repository"
    }
    $headOutput = @(Invoke-GitCapture -GitExecutable $GitExecutable -Repository $Repository -GitArgs @('rev-parse', '--verify', 'HEAD^{commit}'))
    if ($headOutput.Count -lt 1) {
        throw "Could not read source repository HEAD: $Repository"
    }

    $trackedOutput = @(Invoke-GitCapture -GitExecutable $GitExecutable -Repository $Repository -GitArgs @('-c', 'core.quotepath=false', 'ls-files', '--cached'))
    $untrackedOutput = @(Invoke-GitCapture -GitExecutable $GitExecutable -Repository $Repository -GitArgs @('-c', 'core.quotepath=false', 'ls-files', '--others', '--exclude-standard'))
    $tracked = [ordered]@{}
    $untracked = [ordered]@{}

    foreach ($relativePath in $trackedOutput) {
        $relative = [string]$relativePath
        if ($relative.Length -eq 0) { continue }
        $absolute = [System.IO.Path]::GetFullPath((Join-Path -Path $Repository -ChildPath $relative))
        if (-not (Test-PathInside -Candidate $absolute -Parent $Repository)) {
            throw "Git returned a tracked path outside the source repository: $relative"
        }
        $tracked[$relative] = Get-FileSha256OrMissing -Path $absolute
    }
    foreach ($relativePath in $untrackedOutput) {
        $relative = [string]$relativePath
        if ($relative.Length -eq 0) { continue }
        $absolute = [System.IO.Path]::GetFullPath((Join-Path -Path $Repository -ChildPath $relative))
        if (-not (Test-PathInside -Candidate $absolute -Parent $Repository)) {
            throw "Git returned an untracked path outside the source repository: $relative"
        }
        $untracked[$relative] = Get-FileSha256OrMissing -Path $absolute
    }

    return [pscustomobject]@{
        Head = ([string]$headOutput[0]).Trim().ToLowerInvariant()
        Tracked = $tracked
        Untracked = $untracked
    }
}

function Compare-SourceSnapshots {
    param($Before, $After)

    $differences = New-Object 'System.Collections.Generic.List[string]'
    if ($Before.Head -ne $After.Head) {
        $differences.Add('HEAD')
    }
    foreach ($kind in @('Tracked', 'Untracked')) {
        $beforeFiles = $Before.$kind
        $afterFiles = $After.$kind
        foreach ($path in $beforeFiles.Keys) {
            if (-not $afterFiles.Contains($path) -or $beforeFiles[$path] -ne $afterFiles[$path]) {
                $differences.Add("$kind/$path")
            }
        }
        foreach ($path in $afterFiles.Keys) {
            if (-not $beforeFiles.Contains($path)) {
                $differences.Add("$kind/$path")
            }
        }
    }
    return $differences.ToArray()
}

function Get-CheckoutCacheCounts {
    param([Parameter(Mandatory = $true)][string] $Checkout)

    $all = @(Get-ChildItem -LiteralPath $Checkout -Force -Recurse -ErrorAction SilentlyContinue)
    return [pscustomobject]@{
        PytestCacheDirectories = @($all | Where-Object { $_.PSIsContainer -and $_.Name -eq '.pytest_cache' }).Count
        PycacheDirectories = @($all | Where-Object { $_.PSIsContainer -and $_.Name -eq '__pycache__' }).Count
        PycFiles = @($all | Where-Object { -not $_.PSIsContainer -and $_.Extension -eq '.pyc' }).Count
    }
}

function Remove-TreeWithoutFollowingLinks {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][string] $Boundary
    )

    if (-not (Test-PathInside -Candidate $Path -Parent $Boundary)) {
        throw "Refusing cleanup outside the validated boundary: $Path"
    }
    if (-not (Test-Path -LiteralPath $Path)) { return }

    $attributes = [System.IO.File]::GetAttributes($Path)
    $isDirectory = ($attributes -band [System.IO.FileAttributes]::Directory) -ne 0
    $isReparsePoint = ($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
    if ($isReparsePoint) {
        if ($isDirectory) {
            [System.IO.Directory]::Delete($Path, $false)
        } else {
            [System.IO.File]::Delete($Path)
        }
        return
    }
    if (-not $isDirectory) {
        [System.IO.File]::Delete($Path)
        return
    }

    foreach ($child in [System.IO.Directory]::EnumerateFileSystemEntries($Path)) {
        Remove-TreeWithoutFollowingLinks -Path $child -Boundary $Boundary
    }
    [System.IO.Directory]::Delete($Path, $false)
}

function Set-ProcessEnvironment {
    param([string] $Name, [AllowNull()][string] $Value)
    [System.Environment]::SetEnvironmentVariable($Name, $Value, [System.EnvironmentVariableTarget]::Process)
}

$runId = [Guid]::NewGuid().ToString('N')
$checkoutName = "checkout-$runId"
$runtimeStateName = "rt-$runId"
$checkoutPath = $null
$runtimeStatePath = $null
$tempRootPath = $null
$sourcePath = $null
$evidencePath = $null
$gitExecutablePath = $null
$pythonExecutablePath = $null
$logPath = $null
$summaryPath = $null
$beforeSnapshot = $null
$afterSnapshot = $null
$sourceDifferences = @()
$cacheCounts = [pscustomobject]@{
    PytestCacheDirectories = 0
    PycacheDirectories = 0
    PycFiles = 0
}
$savedEnvironment = [ordered]@{}
$redirectedEnvironmentNames = @(
    'HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA',
    'XDG_CACHE_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME',
    'TMP', 'TEMP', 'TMPDIR', 'PYTHONUSERBASE', 'PYTHONDONTWRITEBYTECODE', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS',
    'SDL_VIDEODRIVER', 'SDL_AUDIODRIVER'
)
$testExitCode = $null
$testStarted = $false
$fatalError = $null
$cleanupError = $null
$runtimeStateCleanupError = $null
$sourceCheckError = $null
$cleanupSucceeded = $false
$runtimeStateCleanupSucceeded = $true
$evidenceReady = $false

try {
    if (-not (Test-Path -LiteralPath $SourceRepository -PathType Container)) {
        throw "Source repository directory does not exist: $SourceRepository"
    }
    $sourcePath = Get-NormalizedPath -Path (Resolve-Path -LiteralPath $SourceRepository).Path
    if (-not (Test-Path -LiteralPath $EvidenceDirectory -PathType Container) -and (Test-Path -LiteralPath $EvidenceDirectory)) {
        throw "Evidence path exists but is not a directory: $EvidenceDirectory"
    }
    $evidencePath = Resolve-FuturePath -Path $EvidenceDirectory
    if ((Test-PathEqual -Left $sourcePath -Right $evidencePath) -or (Test-PathInside -Candidate $evidencePath -Parent $sourcePath)) {
        throw "Evidence directory must be outside and separate from the source repository: $evidencePath"
    }

    if (-not (Test-Path -LiteralPath $evidencePath -PathType Container)) {
        New-Item -ItemType Directory -Path $evidencePath -Force | Out-Null
    }
    $evidencePath = Get-NormalizedPath -Path (Resolve-Path -LiteralPath $evidencePath).Path
    if ((Test-PathEqual -Left $sourcePath -Right $evidencePath) -or (Test-PathInside -Candidate $evidencePath -Parent $sourcePath)) {
        throw "Evidence directory must be outside and separate from the source repository: $evidencePath"
    }
    $evidenceReady = $true
    $logPath = Join-Path -Path $evidencePath -ChildPath "test-$runId.log"
    $summaryPath = Join-Path -Path $evidencePath -ChildPath "summary-$runId.json"
    $checkoutPath = Join-Path -Path $evidencePath -ChildPath $checkoutName

    $gitExecutablePath = Resolve-NativeExecutable -Name 'git'
    $pythonExecutablePath = Resolve-NativeExecutable -Name $PythonExecutable

    $commitOutput = @(Invoke-GitCapture -GitExecutable $gitExecutablePath -Repository $sourcePath -GitArgs @('rev-parse', '--verify', "$Commit^{commit}"))
    if ($commitOutput.Count -lt 1 -or -not [string]::Equals(([string]$commitOutput[0]).Trim(), $Commit, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "The requested commit is not available as that exact object in the source repository: $Commit"
    }

    $beforeSnapshot = Get-SourceSnapshot -Repository $sourcePath -GitExecutable $gitExecutablePath
    if (Test-Path -LiteralPath $checkoutPath) {
        throw "Generated checkout path unexpectedly already exists: $checkoutPath"
    }

    $cloneArgs = @('clone', '--no-hardlinks', '--no-checkout', '--quiet', $sourcePath, $checkoutPath)
    & $gitExecutablePath @cloneArgs
    $cloneCode = $LASTEXITCODE
    if ($cloneCode -ne 0) { throw "git clone failed with exit code $cloneCode" }

    $checkoutArgs = @('-C', $checkoutPath, 'checkout', '--quiet', '--detach', $Commit)
    & $gitExecutablePath @checkoutArgs
    $checkoutCode = $LASTEXITCODE
    if ($checkoutCode -ne 0) { throw "Checking out pinned commit failed with exit code $checkoutCode" }
    $headOutput = @(Invoke-GitCapture -GitExecutable $gitExecutablePath -Repository $checkoutPath -GitArgs @('rev-parse', '--verify', 'HEAD^{commit}'))
    if ($headOutput.Count -lt 1 -or -not [string]::Equals(([string]$headOutput[0]).Trim(), $Commit, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "The candidate checkout does not match the requested commit: $Commit"
    }

    $tempRootCandidate = [System.IO.Path]::GetTempPath()
    if (-not (Test-Path -LiteralPath $tempRootCandidate -PathType Container)) {
        throw "OS temporary directory does not exist: $tempRootCandidate"
    }
    $tempRootPath = Get-NormalizedPath -Path (Resolve-Path -LiteralPath $tempRootCandidate).Path
    $runtimeStatePath = Join-Path -Path $tempRootPath -ChildPath $runtimeStateName
    if (Test-Path -LiteralPath $runtimeStatePath) {
        throw "Generated runtime-state path unexpectedly already exists: $runtimeStatePath"
    }
    [System.IO.Directory]::CreateDirectory($runtimeStatePath) | Out-Null
    $runtimeParent = Get-NormalizedPath -Path ([System.IO.Path]::GetDirectoryName($runtimeStatePath))
    if (-not (Test-PathEqual -Left $runtimeParent -Right $tempRootPath) -or
        [System.IO.Path]::GetFileName($runtimeStatePath) -ne $runtimeStateName) {
        throw "Generated runtime-state path failed its containment check: $runtimeStatePath"
    }
    $runtimeItem = Get-Item -LiteralPath $runtimeStatePath -Force
    if (($runtimeItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Generated runtime-state directory is a reparse point: $runtimeStatePath"
    }

    $stateRoot = $runtimeStatePath
    $stateDirs = @{
        Home = Join-Path $stateRoot 'home'
        AppData = Join-Path $stateRoot 'appdata'
        LocalAppData = Join-Path $stateRoot 'localappdata'
        XdgCache = Join-Path $stateRoot 'xdg-cache'
        XdgConfig = Join-Path $stateRoot 'xdg-config'
        XdgData = Join-Path $stateRoot 'xdg-data'
        Temp = Join-Path $stateRoot 'tmp'
        PythonUser = Join-Path $stateRoot 'python-user'
    }
    foreach ($directory in $stateDirs.Values) {
        [System.IO.Directory]::CreateDirectory([string]$directory) | Out-Null
    }

    foreach ($name in $redirectedEnvironmentNames) {
        $savedEnvironment[$name] = [System.Environment]::GetEnvironmentVariable($name, [System.EnvironmentVariableTarget]::Process)
    }
    Set-ProcessEnvironment -Name 'HOME' -Value $stateDirs.Home
    Set-ProcessEnvironment -Name 'USERPROFILE' -Value $stateDirs.Home
    Set-ProcessEnvironment -Name 'APPDATA' -Value $stateDirs.AppData
    Set-ProcessEnvironment -Name 'LOCALAPPDATA' -Value $stateDirs.LocalAppData
    Set-ProcessEnvironment -Name 'XDG_CACHE_HOME' -Value $stateDirs.XdgCache
    Set-ProcessEnvironment -Name 'XDG_CONFIG_HOME' -Value $stateDirs.XdgConfig
    Set-ProcessEnvironment -Name 'XDG_DATA_HOME' -Value $stateDirs.XdgData
    Set-ProcessEnvironment -Name 'TMP' -Value $stateDirs.Temp
    Set-ProcessEnvironment -Name 'TEMP' -Value $stateDirs.Temp
    Set-ProcessEnvironment -Name 'TMPDIR' -Value $stateDirs.Temp
    Set-ProcessEnvironment -Name 'PYTHONUSERBASE' -Value $stateDirs.PythonUser
    Set-ProcessEnvironment -Name 'PYTHONDONTWRITEBYTECODE' -Value '1'
    Set-ProcessEnvironment -Name 'PYTEST_ADDOPTS' -Value $null
    Set-ProcessEnvironment -Name 'PYTEST_PLUGINS' -Value $null
    Set-ProcessEnvironment -Name 'SDL_VIDEODRIVER' -Value 'dummy'
    Set-ProcessEnvironment -Name 'SDL_AUDIODRIVER' -Value 'dummy'

    $pythonArgs = @('-B', '-m', 'pytest', '-p', 'no:cacheprovider', '-o', 'addopts=', '-q', '.')
    $logHeader = @(
        "Run ID: $runId",
        "Source repository: $sourcePath",
        "Pinned commit: $Commit",
        "Checkout: $checkoutPath",
        "Python: $pythonExecutablePath",
        "Fixed Python arguments: $($pythonArgs -join ' ')"
    ) -join [Environment]::NewLine
    Set-Content -LiteralPath $logPath -Value $logHeader -Encoding UTF8
    Push-Location -LiteralPath $checkoutPath
    try {
        $testStarted = $true
        try {
            & $pythonExecutablePath @pythonArgs *>> $logPath
            $testExitCode = [int]$LASTEXITCODE
        } catch {
            $_ | Out-String | Add-Content -LiteralPath $logPath -Encoding UTF8
            $testExitCode = 1
            throw "Could not run the test command. See log: $logPath. $($_.Exception.Message)"
        }
    } finally {
        Pop-Location
    }
} catch {
    $fatalError = $_.Exception.Message
    if ($evidenceReady -and $logPath -and -not (Test-Path -LiteralPath $logPath)) {
        Set-Content -LiteralPath $logPath -Value "Runner error: $fatalError" -Encoding UTF8
    } elseif ($evidenceReady -and $logPath) {
        Add-Content -LiteralPath $logPath -Value "`r`nRunner error: $fatalError" -Encoding UTF8
    }
} finally {
    if ($checkoutPath -and (Test-Path -LiteralPath $checkoutPath)) {
        try {
            $cacheCounts = Get-CheckoutCacheCounts -Checkout $checkoutPath
        } catch {
            $countError = "Could not count checkout cache artifacts: $($_.Exception.Message)"
            if ($fatalError) { $fatalError = "$fatalError; $countError" } else { $fatalError = $countError }
        }
    }

    if ($sourcePath -and $gitExecutablePath -and $beforeSnapshot) {
        try {
            $afterSnapshot = Get-SourceSnapshot -Repository $sourcePath -GitExecutable $gitExecutablePath
            $sourceDifferences = @(Compare-SourceSnapshots -Before $beforeSnapshot -After $afterSnapshot)
        } catch {
            $sourceCheckError = $_.Exception.Message
        }
    }

    foreach ($name in $savedEnvironment.Keys) {
        try {
            Set-ProcessEnvironment -Name $name -Value $savedEnvironment[$name]
        } catch {
            $restoreError = "Could not restore process environment variable ${name}: $($_.Exception.Message)"
            if ($fatalError) { $fatalError = "$fatalError; $restoreError" } else { $fatalError = $restoreError }
        }
    }

    if ($runtimeStatePath -and (Test-Path -LiteralPath $runtimeStatePath)) {
        try {
            $runtimeParent = Get-NormalizedPath -Path ([System.IO.Path]::GetDirectoryName($runtimeStatePath))
            $runtimeLeaf = [System.IO.Path]::GetFileName($runtimeStatePath)
            if (-not (Test-PathEqual -Left $runtimeParent -Right $tempRootPath) -or $runtimeLeaf -ne $runtimeStateName) {
                throw "Generated runtime-state directory failed the cleanup containment check: $runtimeStatePath"
            }
            $runtimeItem = Get-Item -LiteralPath $runtimeStatePath -Force
            if (-not $runtimeItem.PSIsContainer) {
                throw "Generated runtime-state path is no longer a directory: $runtimeStatePath"
            }
            Remove-TreeWithoutFollowingLinks -Path $runtimeStatePath -Boundary $tempRootPath
            $runtimeStateCleanupSucceeded = -not (Test-Path -LiteralPath $runtimeStatePath)
            if (-not $runtimeStateCleanupSucceeded) {
                throw "Generated runtime-state directory still exists after cleanup: $runtimeStatePath"
            }
        } catch {
            $runtimeStateCleanupSucceeded = $false
            $runtimeStateCleanupError = $_.Exception.Message
        }
    } else {
        $runtimeStateCleanupSucceeded = $true
    }

    if ($checkoutPath -and (Test-Path -LiteralPath $checkoutPath)) {
        try {
            $checkoutParent = Get-NormalizedPath -Path ([System.IO.Path]::GetDirectoryName($checkoutPath))
            $checkoutLeaf = [System.IO.Path]::GetFileName($checkoutPath)
            if (-not (Test-PathEqual -Left $checkoutParent -Right $evidencePath) -or $checkoutLeaf -ne $checkoutName) {
                throw "Generated checkout failed the cleanup containment check: $checkoutPath"
            }
            $checkoutItem = Get-Item -LiteralPath $checkoutPath -Force
            if (($checkoutItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Generated checkout is a reparse point; refusing recursive cleanup: $checkoutPath"
            }
            Remove-TreeWithoutFollowingLinks -Path $checkoutPath -Boundary $evidencePath
            $cleanupSucceeded = -not (Test-Path -LiteralPath $checkoutPath)
            if (-not $cleanupSucceeded) { throw "Generated checkout still exists after cleanup: $checkoutPath" }
        } catch {
            $cleanupError = $_.Exception.Message
        }
    } else {
        $cleanupSucceeded = $true
    }

    if ($evidenceReady -and $summaryPath) {
        $hasCacheArtifacts = ($cacheCounts.PytestCacheDirectories -gt 0 -or $cacheCounts.PycacheDirectories -gt 0 -or $cacheCounts.PycFiles -gt 0)
        $sourceIntegrityFailed = ($sourceCheckError -or $sourceDifferences.Count -gt 0)
        $summaryStatus = 'passed'
        if (-not $testStarted -or $fatalError -or $cleanupError -or $runtimeStateCleanupError -or -not $runtimeStateCleanupSucceeded -or $sourceIntegrityFailed -or $hasCacheArtifacts) {
            $summaryStatus = 'error'
        } elseif ($testExitCode -ne 0) {
            $summaryStatus = 'failed'
        }
        $summary = [ordered]@{
            RunId = $runId
            Status = $summaryStatus
            SourceRepository = $sourcePath
            PinnedCommit = $Commit
            CandidateCheckout = $checkoutPath
            RuntimeStateDirectory = $runtimeStatePath
            CapturedTempRoot = $tempRootPath
            PythonExecutable = $pythonExecutablePath
            TestScope = 'repository root'
            PythonArguments = if ($pythonExecutablePath) { @('-B', '-m', 'pytest', '-p', 'no:cacheprovider', '-o', 'addopts=', '-q', '.') } else { @() }
            TestStarted = $testStarted
            TestExitCode = $testExitCode
            RunnerError = $fatalError
            TestLog = $logPath
            CacheCountsBeforeCleanup = $cacheCounts
            SourceCommitBefore = if ($beforeSnapshot) { $beforeSnapshot.Head } else { $null }
            SourceCommitAfter = if ($afterSnapshot) { $afterSnapshot.Head } else { $null }
            TrackedFileCountBefore = if ($beforeSnapshot) { $beforeSnapshot.Tracked.Count } else { 0 }
            PreexistingNonIgnoredUntrackedFileCountBefore = if ($beforeSnapshot) { $beforeSnapshot.Untracked.Count } else { 0 }
            SourceDifferences = @($sourceDifferences)
            SourceCheckError = $sourceCheckError
            SourceUnchanged = -not $sourceIntegrityFailed
            SourceHashesBefore = if ($beforeSnapshot) { [ordered]@{ Tracked = $beforeSnapshot.Tracked; Untracked = $beforeSnapshot.Untracked } } else { $null }
            SourceHashesAfter = if ($afterSnapshot) { [ordered]@{ Tracked = $afterSnapshot.Tracked; Untracked = $afterSnapshot.Untracked } } else { $null }
            CleanupSucceeded = $cleanupSucceeded
            CleanupError = $cleanupError
            RuntimeStateCleanupSucceeded = $runtimeStateCleanupSucceeded
            RuntimeStateCleanupError = $runtimeStateCleanupError
            CacheArtifactsFree = -not $hasCacheArtifacts
            CheckoutExistsAfterCleanup = if ($checkoutPath) { Test-Path -LiteralPath $checkoutPath } else { $false }
        }
        try {
            $summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
        } catch {
            if (-not $fatalError) { $fatalError = "Could not write summary artifact: $($_.Exception.Message)" }
        }
    }
    if ($hadNativeCommandPreference) {
        $PSNativeCommandUseErrorActionPreference = $savedNativeCommandPreference
    }
}

$runnerExitCode = 1
if ($testStarted -and $null -ne $testExitCode) {
    $runnerExitCode = [int]$testExitCode
}
$hasCacheArtifacts = ($cacheCounts.PytestCacheDirectories -gt 0 -or $cacheCounts.PycacheDirectories -gt 0 -or $cacheCounts.PycFiles -gt 0)
$sourceIntegrityFailed = ($sourceCheckError -or $sourceDifferences.Count -gt 0)
if ($runnerExitCode -eq 0 -and ($fatalError -or $cleanupError -or $runtimeStateCleanupError -or -not $runtimeStateCleanupSucceeded -or $sourceIntegrityFailed -or $hasCacheArtifacts)) {
    $runnerExitCode = 1
}
if ($fatalError) { [Console]::Error.WriteLine("Runner error: $fatalError") }
if ($sourceCheckError) { [Console]::Error.WriteLine("Source verification error: $sourceCheckError") }
if ($sourceDifferences.Count -gt 0) { [Console]::Error.WriteLine("Source files changed during the run: $($sourceDifferences -join ', ')") }
if ($cleanupError) { [Console]::Error.WriteLine("Checkout cleanup error: $cleanupError") }
if ($runtimeStateCleanupError) { [Console]::Error.WriteLine("Runtime-state cleanup error: $runtimeStateCleanupError") }
if ($hasCacheArtifacts) {
    [Console]::Error.WriteLine("Checkout cache artifacts found before cleanup: pytest=$($cacheCounts.PytestCacheDirectories), pycache=$($cacheCounts.PycacheDirectories), pyc=$($cacheCounts.PycFiles)")
}
if ($testStarted -and $testExitCode -ne 0) {
    [Console]::Error.WriteLine("Pytest exited with code $testExitCode. See log: $logPath")
}
exit $runnerExitCode
