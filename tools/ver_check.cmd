@REM # Windows PowerShell equivalent of the version comparison helpers
@REM #
@REM # Export `uv` requirements (no hashes), drop comments/blank lines, sort, save.
uv export --no-hashes --format requirements-txt | Sort-Object > ver-uv-export.txt
@REM uv export --no-hashes --format requirements-txt `
@REM   | Where-Object { $_ -notmatch '^\s*#' -and $_ -notmatch '^\s*$' } `
@REM   | Sort-Object `
@REM   | Set-Content -LiteralPath ver-uv-export.txt

@REM # Freeze current environment, strip markers/whitespace, sort, save.
uv pip freeze | Sort-Object > ver-pip-freeze.txt
@REM uv pip freeze `
@REM   | ForEach-Object { $_ -replace ';.*$','' -replace '\s+','' } `
@REM   | Sort-Object `
@REM   | Set-Content -LiteralPath ver-pip-freeze.txt
