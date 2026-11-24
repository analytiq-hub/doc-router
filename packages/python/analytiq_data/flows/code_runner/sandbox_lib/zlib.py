"""Pure-Python stand-in for ``zlib`` inside the Code node sandbox.

The CPython WASI build has no ``zlib`` extension module, but PDFs use Flate (zlib) streams
everywhere, so ``pypdf`` needs it. This module is on the sandbox's ``sys.path`` (read-only,
``/sandbox-lib``) and is only found when the interpreter has no real ``zlib``; with the ``local``
runner the real module wins.

Supported: ``decompress``, ``decompressobj`` (``decompress(data, max_length)``, ``flush``,
``unconsumed_tail``, ``unused_data``, ``eof``), ``compress``, ``compressobj``, ``crc32``,
``adler32``, ``error``, ``MAX_WBITS`` and the common constants. ``wbits`` may select a zlib
stream (9..15), raw deflate (-15..-9), gzip (25..31) or auto-detection of zlib / gzip (41..47).

Decompression is a complete RFC 1951 inflater. Compression writes valid but **uncompressed**
("stored") deflate blocks: correct output that any zlib reads, just not smaller.
"""

from binascii import crc32 as _crc32

MAX_WBITS = 15
DEFLATED = 8
DEF_MEM_LEVEL = 8
DEF_BUF_SIZE = 16384
Z_NO_COMPRESSION = 0
Z_BEST_SPEED = 1
Z_BEST_COMPRESSION = 9
Z_DEFAULT_COMPRESSION = -1
Z_DEFAULT_STRATEGY = 0
Z_FILTERED = 1
Z_HUFFMAN_ONLY = 2
Z_RLE = 3
Z_FIXED = 4
Z_NO_FLUSH = 0
Z_PARTIAL_FLUSH = 1
Z_SYNC_FLUSH = 2
Z_FULL_FLUSH = 3
Z_FINISH = 4
Z_BLOCK = 5
Z_TREES = 6
ZLIB_VERSION = "1.3.1-pure-python"
ZLIB_RUNTIME_VERSION = ZLIB_VERSION


class error(Exception):
    pass


def crc32(data, value=0):
    return _crc32(data, value)


def adler32(data, value=1):
    a = value & 0xFFFF
    b = (value >> 16) & 0xFFFF
    view = memoryview(data)
    for start in range(0, len(view), 5552):  # largest n with no overflow before the modulo
        for byte in view[start:start + 5552]:
            a += byte
            b += a
        a %= 65521
        b %= 65521
    return (b << 16) | a


# ---- Inflate (RFC 1951) ---------------------------------------------------------------------------

_LEN_BASE = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99,
             115, 131, 163, 195, 227, 258)
_LEN_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0)
_DIST_BASE = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025,
              1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577)
_DIST_EXTRA = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12,
               12, 13, 13)
_CL_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)


class _Incomplete(Exception):
    """The input ended before the stream did; ``output`` is what decoded so far."""

    output = b""


def _build(lengths):
    """Huffman lookup table: index = next ``max_len`` input bits (LSB first) -> (symbol, length)."""
    max_len = max(lengths) if lengths else 0
    if max_len == 0:
        return None, 0
    counts = [0] * (max_len + 1)
    for n in lengths:
        if n:
            counts[n] += 1
    left = 1
    for n in range(1, max_len + 1):
        left = (left << 1) - counts[n]
        if left < 0:
            raise error("invalid code lengths set")
    code = 0
    next_code = [0] * (max_len + 2)
    for n in range(1, max_len + 1):
        code = (code + counts[n - 1]) << 1
        next_code[n] = code
    size = 1 << max_len
    table = [None] * size
    for symbol, n in enumerate(lengths):
        if not n:
            continue
        c = next_code[n]
        next_code[n] += 1
        rev = 0
        for _ in range(n):
            rev = (rev << 1) | (c & 1)
            c >>= 1
        entry = (symbol, n)
        for idx in range(rev, size, 1 << n):
            table[idx] = entry
    return table, max_len


_FIXED_LIT = _build([8] * 144 + [9] * 112 + [7] * 24 + [8] * 8)
_FIXED_DIST = _build([5] * 30)


class _Inflater:
    """Decodes one complete deflate stream from ``data`` starting at byte ``pos``."""

    def __init__(self, data, pos, out):
        self.data = data
        self.pos = pos
        self.bitbuf = 0
        self.bitcnt = 0
        self.out = out

    def _need(self, n):
        data, pos = self.data, self.pos
        while self.bitcnt < n:
            if pos >= len(data):
                self.pos = pos
                raise _Incomplete()
            self.bitbuf |= data[pos] << self.bitcnt
            pos += 1
            self.bitcnt += 8
        self.pos = pos

    def bits(self, n):
        if n == 0:
            return 0
        if self.bitcnt < n:
            self._need(n)
        value = self.bitbuf & ((1 << n) - 1)
        self.bitbuf >>= n
        self.bitcnt -= n
        return value

    def decode(self, huff):
        table, max_len = huff
        if table is None:
            raise error("invalid code -- missing end-of-block")
        if self.bitcnt < max_len:
            data, pos = self.data, self.pos
            while self.bitcnt < max_len and pos < len(data):
                self.bitbuf |= data[pos] << self.bitcnt
                pos += 1
                self.bitcnt += 8
            self.pos = pos
        entry = table[self.bitbuf & ((1 << max_len) - 1)]
        if entry is None:
            if self.bitcnt < max_len:
                raise _Incomplete()
            raise error("invalid code")
        symbol, n = entry
        if n > self.bitcnt:
            raise _Incomplete()
        self.bitbuf >>= n
        self.bitcnt -= n
        return symbol

    def align(self):
        drop = self.bitcnt & 7
        self.bitbuf >>= drop
        self.bitcnt -= drop

    def run(self):
        while True:
            final = self.bits(1)
            kind = self.bits(2)
            if kind == 0:
                self._stored()
            elif kind == 1:
                self._codes(_FIXED_LIT, _FIXED_DIST)
            elif kind == 2:
                lit, dist = self._dynamic()
                self._codes(lit, dist)
            else:
                raise error("invalid block type")
            if final:
                break
        # Give back whole bytes read ahead into the bit buffer.
        self.align()
        self.pos -= self.bitcnt // 8
        self.bitbuf = 0
        self.bitcnt = 0
        return self.pos

    def _stored(self):
        self.align()
        length = self.bits(16)
        nlength = self.bits(16)
        if length != (~nlength & 0xFFFF):
            raise error("invalid stored block lengths")
        # Byte-aligned now; give back whole bytes read ahead into the bit buffer.
        self.pos -= self.bitcnt // 8
        self.bitbuf = 0
        self.bitcnt = 0
        end = self.pos + length
        if end > len(self.data):
            self.out += self.data[self.pos:]
            self.pos = len(self.data)
            raise _Incomplete()
        self.out += self.data[self.pos:end]
        self.pos = end

    def _dynamic(self):
        nlen = self.bits(5) + 257
        ndist = self.bits(5) + 1
        ncode = self.bits(4) + 4
        if nlen > 286 or ndist > 30:
            raise error("too many length or distance symbols")
        cl = [0] * 19
        for i in range(ncode):
            cl[_CL_ORDER[i]] = self.bits(3)
        cl_huff = _build(cl)
        lengths = []
        total = nlen + ndist
        while len(lengths) < total:
            sym = self.decode(cl_huff)
            if sym < 16:
                lengths.append(sym)
            elif sym == 16:
                if not lengths:
                    raise error("invalid bit length repeat")
                lengths.extend([lengths[-1]] * (3 + self.bits(2)))
            elif sym == 17:
                lengths.extend([0] * (3 + self.bits(3)))
            else:
                lengths.extend([0] * (11 + self.bits(7)))
        if len(lengths) > total:
            raise error("invalid bit length repeat")
        if lengths[256] == 0:
            raise error("invalid code -- missing end-of-block")
        return _build(lengths[:nlen]), _build(lengths[nlen:])

    def _codes(self, lit, dist):
        out = self.out
        while True:
            sym = self.decode(lit)
            if sym < 256:
                out.append(sym)
            elif sym == 256:
                return
            else:
                sym -= 257
                if sym >= 29:
                    raise error("invalid literal/length code")
                length = _LEN_BASE[sym] + self.bits(_LEN_EXTRA[sym])
                dsym = self.decode(dist)
                if dsym >= 30:
                    raise error("invalid distance code")
                distance = _DIST_BASE[dsym] + self.bits(_DIST_EXTRA[dsym])
                if distance > len(out):
                    raise error("invalid distance too far back")
                start = len(out) - distance
                if distance >= length:
                    out += out[start:start + length]
                else:
                    for i in range(length):
                        out.append(out[start + i])


def _wbits_format(wbits):
    if -15 <= wbits <= -8:
        return "raw"
    if 8 <= wbits <= 15 or wbits == 0:
        return "zlib"
    if 24 <= wbits <= 31:
        return "gzip"
    if 40 <= wbits <= 47:
        return "auto"
    raise ValueError("Invalid initialization option")


def _gzip_header_end(data):
    if len(data) < 10:
        raise _Incomplete()
    if data[0] != 0x1F or data[1] != 0x8B or data[2] != 8:
        raise error("incorrect header check")
    flags = data[3]
    pos = 10
    if flags & 4:
        if len(data) < pos + 2:
            raise _Incomplete()
        pos += 2 + (data[pos] | (data[pos + 1] << 8))
    for bit in (8, 16):
        if flags & bit:
            end = data.find(b"\0", pos)
            if end < 0:
                raise _Incomplete()
            pos = end + 1
    if flags & 2:
        pos += 2
    if pos > len(data):
        raise _Incomplete()
    return pos


def _inflate_all(data, fmt):
    """(output, end position) for the stream at the start of ``data``; ``_Incomplete`` carries output."""
    out = bytearray()
    pos = 0
    if fmt == "auto":
        fmt = "gzip" if data[:2] == b"\x1f\x8b" else "zlib"
    if fmt == "zlib":
        if len(data) < 2:
            raise _Incomplete()
        cmf, flg = data[0], data[1]
        if (cmf & 0x0F) != 8 or ((cmf << 8) | flg) % 31:
            raise error("incorrect header check")
        if flg & 0x20:
            raise error("need dictionary")
        pos = 2
    elif fmt == "gzip":
        pos = _gzip_header_end(data)
    inflater = _Inflater(data, pos, out)
    try:
        pos = inflater.run()
    except _Incomplete as e:
        e.output = out
        raise
    if fmt == "zlib":
        if len(data) < pos + 4:
            e = _Incomplete()
            e.output = out
            raise e
        if int.from_bytes(data[pos:pos + 4], "big") != adler32(out):
            raise error("incorrect data check")
        pos += 4
    elif fmt == "gzip":
        if len(data) < pos + 8:
            e = _Incomplete()
            e.output = out
            raise e
        if int.from_bytes(data[pos:pos + 4], "little") != crc32(out):
            raise error("incorrect data check")
        pos += 8
    return out, pos


def decompress(data, /, wbits=MAX_WBITS, bufsize=DEF_BUF_SIZE):
    try:
        out, _end = _inflate_all(bytes(data), _wbits_format(wbits))
    except _Incomplete:
        raise error("Error -5 while decompressing data: incomplete or truncated stream") from None
    return bytes(out)


class _Decompress:
    """``zlib.decompressobj()``: buffers input and decodes it when it is complete.

    Output for a stream prefix is returned as soon as it decodes, so byte-by-byte feeding works
    (at quadratic cost: meant for small or recovery inputs).
    """

    def __init__(self, wbits=MAX_WBITS, zdict=b""):
        if zdict:
            raise error("preset dictionaries are not supported")
        self._fmt = _wbits_format(wbits)
        self._buf = bytearray()
        self._out = b""
        self._given = 0
        self.unused_data = b""
        self.unconsumed_tail = b""
        self.eof = False

    def _emit(self, max_length):
        pending = self._out[self._given:]
        if max_length and len(pending) > max_length:
            pending = pending[:max_length]
        self._given += len(pending)
        return pending

    def decompress(self, data, /, max_length=0):
        if max_length < 0:
            raise ValueError("max_length must be non-negative")
        if self.eof:
            self.unused_data += bytes(data)
            return b""
        self._buf += data
        try:
            out, end = _inflate_all(bytes(self._buf), self._fmt)
        except _Incomplete as e:
            self._out = bytes(e.output)
        else:
            self._out = bytes(out)
            self.eof = True
            self.unused_data = bytes(self._buf[end:])
            self._buf = bytearray()
        result = self._emit(max_length)
        # Output held back by ``max_length`` stands for input not yet consumed.
        self.unconsumed_tail = b"\0" if self._given < len(self._out) else b""
        return result

    def flush(self, length=DEF_BUF_SIZE):
        result = self._out[self._given:]
        self._given = len(self._out)
        self.unconsumed_tail = b""
        return result

    def copy(self):
        other = _Decompress.__new__(_Decompress)
        other.__dict__.update(self.__dict__)
        other._buf = bytearray(self._buf)
        return other


def decompressobj(wbits=MAX_WBITS, zdict=b""):
    return _Decompress(wbits, zdict)


# ---- Compress (stored blocks) ---------------------------------------------------------------------


def _stored_deflate(data, final=True):
    out = bytearray()
    view = memoryview(data)
    if not view:
        out += bytes((1 if final else 0, 0, 0, 0xFF, 0xFF))
        return out
    for start in range(0, len(view), 0xFFFF):
        chunk = view[start:start + 0xFFFF]
        last = final and start + 0xFFFF >= len(view)
        n = len(chunk)
        out.append(1 if last else 0)
        out += n.to_bytes(2, "little") + (n ^ 0xFFFF).to_bytes(2, "little")
        out += chunk
    return out


def _wrap(raw, data, fmt):
    if fmt == "raw":
        return bytes(raw)
    if fmt == "gzip":
        header = b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\xff"
        trailer = crc32(data).to_bytes(4, "little") + (len(data) & 0xFFFFFFFF).to_bytes(4, "little")
        return header + bytes(raw) + trailer
    return b"\x78\x01" + bytes(raw) + adler32(data).to_bytes(4, "big")


def compress(data, /, level=Z_DEFAULT_COMPRESSION, wbits=MAX_WBITS):
    if not -1 <= level <= 9:
        raise error("Bad compression level")
    data = bytes(data)
    fmt = _wbits_format(wbits)
    if fmt == "auto":
        raise ValueError("Invalid initialization option")
    return _wrap(_stored_deflate(data), data, fmt)


class _Compress:
    def __init__(self, level=Z_DEFAULT_COMPRESSION, method=DEFLATED, wbits=MAX_WBITS, *_args, **_kw):
        if not -1 <= level <= 9:
            raise error("Bad compression level")
        self._fmt = _wbits_format(wbits)
        self._buf = bytearray()
        self._done = False

    def compress(self, data, /):
        if self._done:
            raise error("compressor already flushed")
        self._buf += data
        return b""

    def flush(self, mode=Z_FINISH):
        if mode != Z_FINISH:
            return b""
        self._done = True
        data = bytes(self._buf)
        self._buf = bytearray()
        return _wrap(_stored_deflate(data), data, self._fmt)


def compressobj(level=Z_DEFAULT_COMPRESSION, method=DEFLATED, wbits=MAX_WBITS, memLevel=DEF_MEM_LEVEL,
                strategy=Z_DEFAULT_STRATEGY, zdict=None):
    if zdict:
        raise error("preset dictionaries are not supported")
    return _Compress(level, method, wbits)
