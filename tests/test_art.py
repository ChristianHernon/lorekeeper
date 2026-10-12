import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import art, box  # noqa: E402


def test_every_icon_size_is_drawn_exactly():
    for size, (grid, k) in art.SIZES.items():
        assert len({len(r) for r in grid if r}) == 1, size
        assert max(len(r) for r in grid) * k <= size and len(grid) * k <= size, size
        img = art.image(size)
        assert img.size == (size, size)
        assert img.getpixel((size // 2, size // 2))[3] == 255   # the spine, opaque


def test_box_text_has_no_emoji_left():
    assert box.plain('👂 Listening…') == ('mic', 'Listening…')
    assert box.plain('🎧 Elden Ring…') == ('mic', 'Elden Ring…')
    assert box.plain('🎬 Clipped.') == (None, 'Clipped.')
    assert box.plain('Nice ✨ find 👍🏽 there') == (None, 'Nice find there')
    assert box.plain('') == (None, '')
