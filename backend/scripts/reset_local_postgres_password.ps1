<#
.SYNOPSIS
    Recover a forgotten local PostgreSQL superuser password, and create the
    role + database AREA-303 needs.

.DESCRIPTION
    The documented PostgreSQL recovery route: temporarily switch local
    authentication to `trust`, connect without a password, set a new one, then
    put the original authentication back.

    This is for a PostgreSQL instance on your own machine that you administer.
    It needs an elevated shell because the config lives under Program Files and
    the service has to be restarted.

    SAFETY — the reason this is a script and not a list of steps:

    While `trust` is active, ANY local process can connect as superuser without a
    password. That window must be small and must close even if something fails
    halfway. So the rewrite happens inside try/finally: the original pg_hba.conf
    is restored and the service restarted on any error, on a thrown exception,
    and on Ctrl-C. The script also verifies at the end that `trust` is gone, and
    shouts if it isn't.

    A timestamped backup of pg_hba.conf is kept either way.

.EXAMPLE
    # Run in an ELEVATED PowerShell (Run as Administrator):
    cd d:\arena\AREA-303\backend
    .\scripts\reset_local_postgres_password.ps1

.EXAMPLE
    # Only create the area303 role/database, leave the postgres password alone
    # (you'd still not know it, but AREA-303 doesn't need it):
    .\scripts\reset_local_postgres_password.ps1 -SkipPasswordReset
#>
[CmdletBinding()]
param(
    [string]$ServiceName = "postgresql-x64-18",
    [string]$PgBin = "C:\Program Files\PostgreSQL\18\bin",
    [int]$Port = 5432,
    # Set to skip resetting the superuser password; the area303 role/database is
    # still created, which is all AREA-303 actually needs.
    [switch]$SkipPasswordReset,
    # AREA-303's own role/database. Must match backend/.env (defaults in
    # app/core/config.py are area303/area303/area303).
    [string]$AppRole = "area303",
    [string]$AppPassword = "area303",
    [string]$AppDatabase = "area303"
)

$ErrorActionPreference = "Stop"

function Assert-Elevated {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Script nay can quyen Administrator. Mo PowerShell bang 'Run as administrator' roi chay lai."
    }
}

function Get-DataDir {
    param([string]$Name)
    $path = (Get-CimInstance Win32_Service -Filter "Name='$Name'").PathName
    if (-not $path) { throw "Khong tim thay service '$Name'." }
    # PathName looks like: "...\pg_ctl.exe" runservice -N "..." -D "C:\...\data" -w
    if ($path -notmatch '-D\s+"([^"]+)"') { throw "Khong doc duoc data dir tu: $path" }
    return $Matches[1]
}

# pg_hba.conf is parsed as plain text; a UTF-8 BOM can break it, and
# Set-Content/Out-File add one. Write bytes explicitly instead.
function Write-NoBom {
    param([string]$Path, [string[]]$Lines)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllLines($Path, $Lines, $utf8NoBom)
}

function Restart-Pg {
    param([string]$Name)
    Restart-Service -Name $Name -Force
    # Service "running" precedes "accepting connections" — poll pg_isready
    # rather than sleeping a guessed amount.
    $isReady = Join-Path $PgBin "pg_isready.exe"
    for ($i = 0; $i -lt 30; $i++) {
        & $isReady -h localhost -p $Port -q 2>$null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "PostgreSQL khong nhan ket noi sau khi restart."
}

function Invoke-Sql {
    param([string]$Sql, [string]$Database = "postgres")
    $psql = Join-Path $PgBin "psql.exe"
    # No PGPASSWORD: during the trust window none is needed, and setting one
    # would mask a pg_hba rewrite that silently didn't apply.
    $out = & $psql -h localhost -p $Port -U postgres -d $Database -v ON_ERROR_STOP=1 -c $Sql 2>&1
    if ($LASTEXITCODE -ne 0) { throw "psql that bai:`n$out" }
    return $out
}

Assert-Elevated

$dataDir = Get-DataDir -Name $ServiceName
$hba = Join-Path $dataDir "pg_hba.conf"
if (-not (Test-Path $hba)) { throw "Khong thay $hba" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = "$hba.bak-$stamp"
Copy-Item $hba $backup
Write-Host "Da backup pg_hba.conf -> $backup" -ForegroundColor Cyan

$original = Get-Content $hba
$restored = $false

try {
    # Only local/loopback rules are relaxed. Remote rules, if any, are untouched.
    $patched = $original | ForEach-Object {
        if ($_ -match '^\s*local\s' -or $_ -match '^\s*host\s+\S+\s+\S+\s+(127\.0\.0\.1/32|::1/128)\s') {
            $_ -replace '(scram-sha-256|md5|password|peer|ident)\s*$', 'trust'
        }
        else { $_ }
    }
    Write-NoBom -Path $hba -Lines $patched
    Write-Host "Da tam chuyen xac thuc local sang 'trust'." -ForegroundColor Yellow
    Restart-Pg -Name $ServiceName

    if (-not $SkipPasswordReset) {
        $secure = Read-Host "Mat khau MOI cho user 'postgres'" -AsSecureString
        $confirm = Read-Host "Nhap lai" -AsSecureString
        $p1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
        $p2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($confirm))
        if ($p1 -ne $p2) { throw "Hai lan nhap khong giong nhau. Khong doi gi ca." }
        if ([string]::IsNullOrWhiteSpace($p1)) { throw "Mat khau rong. Khong doi gi ca." }
        # Single-quote escaping for the SQL literal.
        $escaped = $p1.Replace("'", "''")
        Invoke-Sql -Sql "ALTER USER postgres PASSWORD '$escaped';" | Out-Null
        Write-Host "Da dat lai mat khau cho 'postgres'." -ForegroundColor Green
    }

    # AREA-303's role + database, so the app never needs the superuser password.
    $roleSql = @"
DO `$`$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$AppRole') THEN
        CREATE ROLE $AppRole LOGIN PASSWORD '$AppPassword';
    ELSE
        ALTER ROLE $AppRole LOGIN PASSWORD '$AppPassword';
    END IF;
END
`$`$;
"@
    Invoke-Sql -Sql $roleSql | Out-Null
    Write-Host "Role '$AppRole' san sang." -ForegroundColor Green

    $exists = Invoke-Sql -Sql "SELECT 1 FROM pg_database WHERE datname = '$AppDatabase';"
    if ($exists -match '\(1 row\)') {
        Write-Host "Database '$AppDatabase' da ton tai." -ForegroundColor Green
    }
    else {
        # CREATE DATABASE cannot run inside a transaction or a DO block.
        Invoke-Sql -Sql "CREATE DATABASE $AppDatabase OWNER $AppRole ENCODING 'UTF8';" | Out-Null
        Write-Host "Da tao database '$AppDatabase'." -ForegroundColor Green
    }
}
finally {
    # Runs on success, on error, and on Ctrl-C. Leaving 'trust' in place would
    # mean any local process could connect as superuser.
    Write-NoBom -Path $hba -Lines $original
    try {
        Restart-Pg -Name $ServiceName
        $restored = $true
    }
    catch {
        Write-Host "CANH BAO: khong restart duoc service sau khi phuc hoi pg_hba.conf." -ForegroundColor Red
    }
    Write-Host "Da phuc hoi pg_hba.conf ve nguyen ban." -ForegroundColor Cyan
}

# Verify rather than assume: a restore that didn't apply is the one failure mode
# that leaves the database wide open.
$now = Get-Content $hba
$stillTrust = $now | Where-Object {
    ($_ -match '^\s*local\s' -or $_ -match '^\s*host\s') -and $_ -match '\btrust\s*$'
}
if ($stillTrust) {
    Write-Host ""
    Write-Host "NGUY HIEM: pg_hba.conf van con dong 'trust':" -ForegroundColor Red
    $stillTrust | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host "Sua tay ngay, hoac copy lai tu $backup" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Xong. Xac thuc local da tro ve scram-sha-256." -ForegroundColor Green
if (-not $restored) {
    Write-Host "Nho khoi dong lai service '$ServiceName' bang tay." -ForegroundColor Yellow
}
Write-Host "Buoc tiep theo: quay lai Claude, no se chay alembic upgrade head."
