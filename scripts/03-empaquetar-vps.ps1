<#
  Empaqueta el proyecto para desplegarlo en un VPS (Windows PowerShell).

    powershell -ExecutionPolicy Bypass -File scripts\03-empaquetar-vps.ps1

  Genera dist\vps\ con:
    - mapa-imagenes.tar.gz : las 3 imagenes Docker ya construidas
    - el proyecto (compose, codigo, PBF y MBTiles) listo para descomprimir en el VPS
    - SHA256SUMS.txt       : sumas para verificar la copia
#>
$ErrorActionPreference = 'Stop'

$raiz = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $raiz 'dist\vps'
$proyecto = Join-Path $dist 'proyecto'
$imagenes = @('mapas-nominatim:5.3.3', 'mapas-photon:1.3.0', 'mapas-tileserver:1.0.0')

Set-Location $raiz

Write-Host '==> Comprobando imagenes'
foreach ($img in $imagenes) {
  docker image inspect $img *> $null
  if ($LASTEXITCODE -ne 0) {
    throw "Falta la imagen $img. Construyela con: docker compose build"
  }
}

Write-Host "==> Preparando $dist"
if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
New-Item -ItemType Directory -Force -Path $proyecto | Out-Null
foreach ($d in @('data', 'geocoder', 'tileserver', 'tilemaker', 'scripts', 'deploy\vps')) {
  New-Item -ItemType Directory -Force -Path (Join-Path $proyecto $d) | Out-Null
}

Write-Host '==> Exportando imagenes (docker save) -> ~1.8 GB'
$tar = Join-Path $dist 'mapa-imagenes.tar'
docker save -o $tar @imagenes
if ($LASTEXITCODE -ne 0) { throw 'docker save fallo' }

# Comprimir con GZip de .NET (mismo formato que el script .sh: gzip plano del tar de docker)
$gz = "$tar.gz"
$in  = [IO.File]::OpenRead($tar)
$out = [IO.File]::Create($gz)
$zs  = New-Object IO.Compression.GZipStream($out, [IO.Compression.CompressionLevel]::Optimal)
$in.CopyTo($zs)
$zs.Dispose(); $out.Dispose(); $in.Dispose()
Remove-Item -Force $tar
Write-Host '    comprimido'

Write-Host '==> Copiando el proyecto'
Copy-Item 'docker-compose.yml', 'docker-compose.vps.yml', 'VPS.md' -Destination $proyecto
Copy-Item 'peru-261020.osm.pbf' -Destination $proyecto
Copy-Item 'data\peru.mbtiles' -Destination (Join-Path $proyecto 'data')
Copy-Item 'geocoder\*' -Destination (Join-Path $proyecto 'geocoder') -Recurse -Force
Copy-Item 'tileserver\*' -Destination (Join-Path $proyecto 'tileserver') -Recurse -Force
Copy-Item 'tilemaker\*' -Destination (Join-Path $proyecto 'tilemaker') -Recurse -Force
Copy-Item 'scripts\*.sh' -Destination (Join-Path $proyecto 'scripts') -Force
Copy-Item 'deploy\vps\*' -Destination (Join-Path $proyecto 'deploy\vps') -Force

Write-Host '==> Calculando sumas'
$lineas = Get-ChildItem -Path $dist -Recurse -File |
  Where-Object { $_.Name -ne 'SHA256SUMS.txt' } |
  ForEach-Object {
    $rel = $_.FullName.Substring($dist.Length + 1).Replace('\', '/')
    '{0}  {1}' -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $rel
  }
$lineas | Set-Content -Encoding ascii (Join-Path $dist 'SHA256SUMS.txt')

$total = [math]::Round((Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host ''
Write-Host "==> Listo: $dist ($total MB)"
Write-Host ''
Write-Host 'Siguiente paso (desde tu PC):'
Write-Host '  scp -r dist/vps/* usuario@TU_VPS:/opt/mapas/'
Write-Host ''
Write-Host 'Y en el VPS:'
Write-Host '  cd /opt/mapas/proyecto && bash deploy/vps/iniciar.sh'
