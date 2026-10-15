$ErrorActionPreference = "Stop"
$docx = "C:\Users\dell\OneDrive\Bureau\Rasoul\FORBIOM-ON_Preliminary_Results_Report_v2.docx"
$pdf = "C:\Users\dell\OneDrive\Bureau\Rasoul\_report_build\preview.pdf"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($docx)
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
    $doc.Save()
    "Pages: " + $doc.ComputeStatistics(2)
    $doc.ExportAsFixedFormat($pdf, 17)
    $doc.Close()
} finally {
    $word.Quit()
}
