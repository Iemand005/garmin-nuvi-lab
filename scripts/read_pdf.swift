// Read-only text extraction and selected-page rendering using macOS PDFKit.
import Foundation
import PDFKit
import AppKit
let args = CommandLine.arguments
guard args.count >= 3, let pdf = PDFDocument(url: URL(fileURLWithPath: args[1])) else {
    fatalError("usage: swift scripts/read_pdf.swift INPUT OUTPUT_PREFIX [PAGE_INDEX ...]")
}
let prefix = args[2]
var text = ""
for i in 0..<pdf.pageCount {
    text += "\n--- PDF PAGE \(i + 1) ---\n" + (pdf.page(at:i)?.string ?? "")
}
try text.write(toFile: prefix + ".txt", atomically: true, encoding: .utf8)
for p in args.dropFirst(3) {
    guard let index = Int(p), let page = pdf.page(at:index) else { continue }
    let bounds = page.bounds(for:.mediaBox)
    let size = NSSize(width:bounds.width*2, height:bounds.height*2)
    let img = page.thumbnail(of:size, for:.mediaBox)
    guard let tiff = img.tiffRepresentation, let rep = NSBitmapImageRep(data:tiff),
          let png = rep.representation(using:.png, properties:[:]) else { continue }
    try png.write(to:URL(fileURLWithPath: prefix + "-page-\(index+1).png"))
}
print("Read \(pdf.pageCount) pages: \(prefix).txt")
