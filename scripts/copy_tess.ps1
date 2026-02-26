Copy-Item -Path "C:\Program Files\Tesseract-OCR" -Destination ".\Tesseract-OCR" -Recurse -Force
Get-ChildItem -Path ".\Tesseract-OCR\tessdata\*.traineddata" | Where-Object { $_.Name -notin @('eng.traineddata', 'osd.traineddata') } | Remove-Item -Force
