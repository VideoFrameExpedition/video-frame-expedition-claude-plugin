# Contact sheets of a reframe plan: every keyframe of every reframed piece with its crop drawn
# over it (outside dimmed, yellow frame; red frame and percentage when the subject's target keeps
# less than the plan's `flag`). Written by reframe.py (review.json + kf/*.jpg); open the sheets
# with Read. Windows PowerShell 5.1, System.Drawing only (no Pillow needed).
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File review_sheet.ps1 -Review OUT_DIR\review.json
param(
    [Parameter(Mandatory = $true)][string]$Review,
    [string]$OutDir = "",
    [int]$RowsPerSheet = 5,
    [switch]$FlaggedOnly
)
Add-Type -AssemblyName System.Drawing
if (-not $OutDir) { $OutDir = Split-Path -Parent (Resolve-Path $Review) }
$data = Get-Content $Review -Raw -Encoding UTF8 | ConvertFrom-Json
$pieces = @($data.pieces)
if ($FlaggedOnly) { $pieces = @($pieces | Where-Object { $_.flags.Count -gt 0 }) }
# Cells fit the keyframes' shape: tall for footage filmed upright, wide for landscape footage
$cellW = 112; $cellH = 196; $labelW = 64; $perRow = 8
$first = @($pieces | ForEach-Object { $_.images } | Where-Object { $_ }) | Select-Object -First 1
if ($first) {
    $probe = [System.Drawing.Image]::FromFile($first.file)
    if ($probe.Width -gt $probe.Height) { $cellW = 236; $cellH = 136 }
    $probe.Dispose()
}
$font = New-Object System.Drawing.Font("Arial", 12, [System.Drawing.FontStyle]::Bold)
$small = New-Object System.Drawing.Font("Arial", 8)
$dim = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(170, 0, 0, 0))
$ok = New-Object System.Drawing.Pen ([System.Drawing.Color]::Yellow), 2
$bad = New-Object System.Drawing.Pen ([System.Drawing.Color]::Red), 3
$sheet = 0
$written = @()
for ($i = 0; $i -lt $pieces.Count; $i += $RowsPerSheet) {
    $sheet++
    $bmp = New-Object System.Drawing.Bitmap ($labelW + $cellW * $perRow), ($cellH * $RowsPerSheet)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::FromArgb(40, 40, 40))
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    for ($r = 0; $r -lt $RowsPerSheet -and ($i + $r) -lt $pieces.Count; $r++) {
        $p = $pieces[$i + $r]; $y0 = $r * $cellH
        $g.DrawString([string]$p.n, $font, [System.Drawing.Brushes]::Yellow, 2, $y0 + 2)
        $flagText = ($p.flags -join "`n")
        if ($flagText) {
            $g.DrawString($flagText, $small, [System.Drawing.Brushes]::Orange,
                (New-Object System.Drawing.RectangleF 2, ($y0 + 22), ($labelW - 4), ($cellH - 26)))
        }
        $k = 0
        foreach ($im in $p.images) {
            if ($k -ge $perRow) { break }
            $img = [System.Drawing.Image]::FromFile($im.file)
            $scale = [math]::Min(($cellW - 4) / $img.Width, ($cellH - 4) / $img.Height)
            $w = [int]($img.Width * $scale); $h = [int]($img.Height * $scale)
            $x = $labelW + $k * $cellW; $y = $y0
            $g.DrawImage($img, $x, $y, $w, $h)
            $img.Dispose()
            $cx = [int]($p.crop[0] * $w); $cy = [int]($p.crop[1] * $h)
            $cw = [int]($p.crop[2] * $w); $ch = [int]($p.crop[3] * $h)
            if ($cy -gt 0) { $g.FillRectangle($dim, $x, $y, $w, $cy) }
            if ($cy + $ch -lt $h) { $g.FillRectangle($dim, $x, $y + $cy + $ch, $w, $h - $cy - $ch) }
            if ($cx -gt 0) { $g.FillRectangle($dim, $x, $y + $cy, $cx, $ch) }
            if ($cx + $cw -lt $w) { $g.FillRectangle($dim, $x + $cx + $cw, $y + $cy, $w - $cx - $cw, $ch) }
            $low = ($im.cov -ne $null) -and ($im.cov -lt $data.flag)
            $pen = if ($low) { $bad } else { $ok }
            $g.DrawRectangle($pen, $x + $cx + 1, $y + $cy + 1, [math]::Max(2, $cw - 2), [math]::Max(2, $ch - 2))
            if ($im.cov -ne $null) {
                $brush = if ($low) { [System.Drawing.Brushes]::Red } else { [System.Drawing.Brushes]::White }
                $g.DrawString(("{0:P0}" -f $im.cov), $small, $brush, $x + 2, $y + $h - 14)
            }
            $k++
        }
    }
    $out = Join-Path $OutDir ("review_{0:D2}.jpg" -f $sheet)
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Jpeg)
    $g.Dispose(); $bmp.Dispose()
    $written += $out
}
$written
