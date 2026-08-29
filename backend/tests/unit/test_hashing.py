import hashlib

from app.services.hashing import sha256_bytes


def test_known_vector_empty_string():
    assert (
        sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_known_vector_abc():
    assert (
        sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_identical_bytes_produce_identical_hash():
    data = b"the quick brown fox jumps over the lazy dog" * 1000
    assert sha256_bytes(data) == sha256_bytes(data)


def test_one_byte_change_produces_different_hash():
    data = bytearray(b"the quick brown fox jumps over the lazy dog")
    original = sha256_bytes(bytes(data))
    data[0] ^= 0xFF
    changed = sha256_bytes(bytes(data))
    assert original != changed


def test_matches_hashlib_reference_across_chunk_boundary():
    # Exercise the chunked implementation across its 1 MiB boundary.
    data = b"x" * (1024 * 1024 + 12345)
    assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()
