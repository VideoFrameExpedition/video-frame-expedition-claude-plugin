// Contact sheets of a reframe plan, on macOS: every keyframe of every reframed piece with its crop
// drawn over it (outside dimmed, yellow frame; red frame and percentage when the subject's target
// keeps less than the plan's `flag`). Written by reframe.py (review.json + kf/*.jpg); open the
// sheets with Read. JavaScript for Automation and AppKit, both part of macOS: nothing to install.
// The same sheets as review_sheet.ps1 on Windows.
//
//   osascript -l JavaScript review_sheet.js OUT_DIR/review.json [--flagged-only] [--rows 5]
//                                           [--out-dir DIR]
ObjC.import("AppKit");

function color(r, g, b, a) {
  return $.NSColor.colorWithCalibratedRedGreenBlueAlpha(r / 255, g / 255, b / 255, a / 255);
}

function loadImage(path) {
  var rep = $.NSBitmapImageRep.imageRepWithContentsOfFile($(path).stringByExpandingTildeInPath);
  return rep.isNil() ? null : rep;
}

function pad2(n) {
  return (n < 10 ? "0" : "") + n;
}

function run(argv) {
  var review = null;
  var outDir = "";
  var rowsPerSheet = 5;
  var flaggedOnly = false;
  for (var a = 0; a < argv.length; a++) {
    if (argv[a] === "--flagged-only") flaggedOnly = true;
    else if (argv[a] === "--rows") rowsPerSheet = parseInt(argv[++a], 10);
    else if (argv[a] === "--out-dir") outDir = argv[++a];
    else review = argv[a];
  }
  if (!review) {
    throw new Error(
      "usage: osascript -l JavaScript review_sheet.js OUT_DIR/review.json " +
        "[--flagged-only] [--rows N] [--out-dir DIR]"
    );
  }
  var reviewPath = $(review).stringByExpandingTildeInPath;
  var text = $.NSString.stringWithContentsOfFileEncodingError(
    reviewPath,
    $.NSUTF8StringEncoding,
    null
  );
  if (text.isNil()) throw new Error("cannot read " + review);
  var data = JSON.parse(text.js);
  if (!outDir) outDir = reviewPath.stringByDeletingLastPathComponent.js;
  outDir = $(outDir).stringByExpandingTildeInPath.js;
  $.NSFileManager.defaultManager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(
    $(outDir),
    true,
    $(),
    null
  );
  var pieces = data.pieces || [];
  if (flaggedOnly) {
    pieces = pieces.filter(function (p) {
      return p.flags && p.flags.length > 0;
    });
  }

  // Cells fit the keyframes' shape: tall for footage filmed upright, wide for landscape footage
  var cellW = 112;
  var cellH = 196;
  var labelW = 64;
  var perRow = 8;
  for (var f = 0; f < pieces.length; f++) {
    if (pieces[f].images && pieces[f].images.length) {
      var probe = loadImage(pieces[f].images[0].file);
      if (probe && probe.pixelsWide > probe.pixelsHigh) {
        cellW = 236;
        cellH = 136;
      }
      break;
    }
  }

  var W = 0;
  var H = 0;
  // AppKit counts y from the bottom: every rectangle below is given from the top, as on Windows
  function rect(x, y, w, h) {
    return $.NSMakeRect(x, H - y - h, w, h);
  }
  function fill(c, r) {
    c.setFill;
    $.NSBezierPath.bezierPathWithRect(r).fill;
  }
  function frame(c, width, r) {
    c.setStroke;
    var path = $.NSBezierPath.bezierPathWithRect(r);
    path.lineWidth = width;
    path.stroke;
  }
  function attrs(font, c) {
    return $.NSDictionary.dictionaryWithObjectsForKeys(
      $([font, c]),
      $([$.NSFontAttributeName, $.NSForegroundColorAttributeName])
    );
  }
  var big = $.NSFont.boldSystemFontOfSize(12);
  var small = $.NSFont.systemFontOfSize(8);
  var yellow = color(255, 255, 0, 255);
  var orange = color(255, 165, 0, 255);
  var red = color(255, 0, 0, 255);
  var lightRed = color(255, 110, 110, 255);
  var labelBack = color(0, 0, 0, 200);
  var white = color(255, 255, 255, 255);
  var dim = color(0, 0, 0, 170);
  var jpegType =
    $.NSBitmapImageFileTypeJPEG !== undefined ? $.NSBitmapImageFileTypeJPEG : 3;

  var written = [];
  var sheet = 0;
  for (var i = 0; i < pieces.length; i += rowsPerSheet) {
    sheet++;
    // The sheet fits what it shows: a smaller picture is easier to read
    var rows = Math.min(rowsPerSheet, pieces.length - i);
    var cols = 1;
    for (var q = 0; q < rows; q++) {
      cols = Math.max(cols, Math.min(perRow, (pieces[i + q].images || []).length));
    }
    W = labelW + cellW * cols;
    H = cellH * rows;
    var canvas =
      $.NSBitmapImageRep.alloc.initWithBitmapDataPlanesPixelsWidePixelsHighBitsPerSampleSamplesPerPixelHasAlphaIsPlanarColorSpaceNameBytesPerRowBitsPerPixel(
        null,
        W,
        H,
        8,
        4,
        true,
        false,
        $.NSDeviceRGBColorSpace,
        0,
        0
      );
    var ctx = $.NSGraphicsContext.graphicsContextWithBitmapImageRep(canvas);
    $.NSGraphicsContext.saveGraphicsState;
    $.NSGraphicsContext.setCurrentContext(ctx);
    if ($.NSImageInterpolationHigh !== undefined) {
      ctx.imageInterpolation = $.NSImageInterpolationHigh;
    }
    fill(color(40, 40, 40, 255), rect(0, 0, W, H));
    for (var r = 0; r < rowsPerSheet && i + r < pieces.length; r++) {
      var p = pieces[i + r];
      var y0 = r * cellH;
      $(String(p.n)).drawInRectWithAttributes(rect(2, y0 + 2, labelW - 4, 18), attrs(big, yellow));
      var flagText = (p.flags || []).join("\n");
      if (flagText) {
        $(flagText).drawInRectWithAttributes(
          rect(2, y0 + 22, labelW - 4, cellH - 26),
          attrs(small, orange)
        );
      }
      var images = p.images || [];
      for (var k = 0; k < images.length && k < perRow; k++) {
        var im = images[k];
        var img = loadImage(im.file);
        if (!img) continue;
        var scale = Math.min((cellW - 4) / img.pixelsWide, (cellH - 4) / img.pixelsHigh);
        var w = Math.round(img.pixelsWide * scale);
        var h = Math.round(img.pixelsHigh * scale);
        var x = labelW + k * cellW;
        var y = y0;
        img.drawInRect(rect(x, y, w, h));
        var cx = Math.round(p.crop[0] * w);
        var cy = Math.round(p.crop[1] * h);
        var cw = Math.round(p.crop[2] * w);
        var ch = Math.round(p.crop[3] * h);
        if (cy > 0) fill(dim, rect(x, y, w, cy));
        if (cy + ch < h) fill(dim, rect(x, y + cy + ch, w, h - cy - ch));
        if (cx > 0) fill(dim, rect(x, y + cy, cx, ch));
        if (cx + cw < w) fill(dim, rect(x + cx + cw, y + cy, w - cx - cw, ch));
        var hasCov = im.cov !== null && im.cov !== undefined;
        var low = hasCov && im.cov < data.flag;
        frame(
          low ? red : yellow,
          low ? 3 : 2,
          rect(x + cx + 1, y + cy + 1, Math.max(2, cw - 2), Math.max(2, ch - 2))
        );
        if (hasCov) {
          // On a dark box: readable over the frame's line and over dark footage
          fill(labelBack, rect(x + 1, y + h - 15, 34, 14));
          $(Math.round(im.cov * 100) + " %").drawInRectWithAttributes(
            rect(x + 3, y + h - 14, 60, 12),
            attrs(small, low ? lightRed : white)
          );
        }
      }
    }
    ctx.flushGraphics;
    $.NSGraphicsContext.restoreGraphicsState;
    var jpeg = canvas.representationUsingTypeProperties(
      jpegType,
      $.NSDictionary.dictionaryWithObjectForKey($(0.85), $.NSImageCompressionFactor)
    );
    var out = $(outDir).stringByAppendingPathComponent("review_" + pad2(sheet) + ".jpg");
    if (jpeg.isNil() || !jpeg.writeToFileAtomically(out, true)) {
      throw new Error("cannot write " + out.js);
    }
    written.push(out.js);
  }
  return written.join("\n");
}
