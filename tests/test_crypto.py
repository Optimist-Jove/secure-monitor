from smd.crypto import derive_key, hash_gui_pin, load_or_create_salt, verify_gui_pin


def test_derive_and_pin():
    salt = b"testsalt12345678"
    key = derive_key("secret", salt)
    assert len(key) > 0
    stored = hash_gui_pin("1234")
    assert verify_gui_pin("1234", stored)
    assert not verify_gui_pin("0000", stored)
