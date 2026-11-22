"""Shared analysis for the demo redesigns (main_pipeline/demo/redesigns/shared.py)."""
import sys

from helpers import ROOT, SyntheticTestCase

sys.path.insert(0, str(ROOT / 'demo' / 'redesigns'))
import shared  # noqa: E402


class DemoSharedTests(SyntheticTestCase):
    def test_runs_the_original_mock_pipeline(self):
        analysis = shared.analyze(self.wav(duration=1.0).read_bytes(), 3)
        self.assertFalse(analysis.pitch_measured)
        self.assertFalse(analysis.timbre_measured)
        self.assertEqual(analysis.voice.span, 'A2–E4')  # the mock fixture, 110-330 Hz
        self.assertEqual([s.rank for s in analysis.songs], [1, 2, 3, None, None])
        self.assertEqual([s.score for s in analysis.recommended], [0.9, 0.8, 0.7])
        self.assertEqual([s.song_id for s in analysis.recommended], ['mock-001', 'mock-002', 'mock-003'])
        # The mock ranker gives every song the same explanation, so it is shown once.
        self.assertIn('fixed fixture score', analysis.caveat)
        self.assertTrue(all(s.reason is None for s in analysis.recommended))
        self.assertEqual(analysis.mfcc, [0.0] * 20)

    def test_mock_songs_have_no_melody_range(self):
        songs = shared.catalog_songs()
        self.assertEqual(len(songs), 5)
        self.assertFalse(any(s.has_range for s in songs))
        self.assertEqual(songs[0].span, 'no melody range')
        self.assertEqual(songs[0].code, '001')
        self.assertEqual(songs[0].name, 'Demo Song 1 (fictional)')

    def test_scale_falls_back_without_ranges_and_labels_notes(self):
        scale = shared.Scale.around(shared.catalog_songs(), None)
        self.assertEqual((scale.low, scale.high), shared.DEFAULT_SPAN)
        voice = shared.Voice(110.0, 330.0, 220.0, 0.8)
        scale = shared.Scale.around(shared.catalog_songs(), voice)
        self.assertTrue(0 < scale.pos(110.0) < scale.pos(330.0) < 1)
        ticks = {name: hz for _, name, hz in scale.ticks()}
        self.assertAlmostEqual(ticks['A3'], 220.0)

    def test_dial_draws_every_layout_with_its_own_gradient(self):
        theme = shared.DialTheme(glass=('#fff', '#eee', '#ddd'), ink='#000', ink_dim='#666', hz_ink='#333',
                                 label='#900', band_glow='#fff', band_fill='#fef', needle='#f00',
                                 display='Serif', display_weight=600, text='Sans', text_weight=500)
        analysis = shared.analyze(self.wav(duration=1.0).read_bytes(), 5)
        svgs = {layout: shared.dial_svg(analysis.songs, analysis, layout, theme) for layout in shared.DIAL_LAYOUTS}
        for layout, svg in svgs.items():
            self.assertTrue(svg.startswith(f'<svg class="{layout}"'))
            self.assertIn(f'id="glass-{layout[0]}"', svg)   # a hidden SVG's gradient must not be shared
            self.assertIn('YOUR BAND A2–E4', svg)
            self.assertIn('no melody range', svg)
        empty = shared.dial_svg(shared.catalog_songs(), None, 'medium', theme)
        self.assertIn('NO SIGNAL', empty)

    def test_fonts_are_inlined(self):
        css = shared.font_css(('Test', 'jost-var.woff2', '400 500', 'normal'))
        self.assertIn('data:font/woff2;base64,', css)
        self.assertIn('font-weight:400 500', css)

    def test_error_advice(self):
        self.assertIn('60 seconds', shared.error_text('audio_too_long'))
        self.assertEqual(shared.error_text('unknown'), 'Check the recording and try again.')
