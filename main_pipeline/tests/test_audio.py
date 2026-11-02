"""Day 3 PCM, container, quality and numerical regression coverage."""
import struct

import numpy as np

from helpers import SyntheticTestCase
from suara.audio.preprocessing import preprocess_audio


class AudioTests(SyntheticTestCase):
    def test_pcm_width_rate_channel_matrix(self):
        for width in (1, 2, 3, 4):
            for rate in (8000, 16000, 44100, 48000):
                for channels in (1, 2):
                    with self.subTest(width=width, rate=rate, channels=channels):
                        audio = preprocess_audio(self.wav(width=width, rate=rate, channels=channels))
                        self.assertEqual((audio.sample_rate, len(audio.waveform), audio.duration_s),
                                         (16000, 8000, 0.5))
                        # Exclude filter edge transients; quantization is largest at PCM8.
                        self.assertAlmostEqual(max(audio.waveform[100:-100]), 0.25, delta=0.01)
                        self.assertTrue(np.isfinite(audio.waveform).all())

    def test_signed_pcm_and_stereo_average(self):
        for width in (1, 2, 3, 4):
            samples = np.tile([[-0.5, 0.25], [0.25, 0.75]], (4000, 1))
            audio = preprocess_audio(self.wav(width=width, channels=2, samples=samples))
            np.testing.assert_array_equal(audio.waveform, np.tile([-0.125, 0.5], 4000))

    def test_duration_endpoints_and_outside(self):
        for duration in (0.5, 60):
            with self.subTest(duration=duration):
                self.assertEqual(preprocess_audio(self.wav(duration=duration)).duration_s, duration)
        for duration, code in ((0, 'invalid_audio'), (0.5 - 1/16000, 'audio_too_short'),
                               (60 + 1/16000, 'audio_too_long')):
            self.assert_error(code, lambda: preprocess_audio(self.wav(duration=duration)))

    def test_silence_and_near_silence(self):
        for amplitude in (0, 1e-6, 1e-5):
            self.assert_error('silent_audio', lambda: preprocess_audio(self.wav(width=4, amplitude=amplitude)))
        self.assertGreater(max(preprocess_audio(self.wav(width=4, amplitude=3e-5)).waveform), 1e-5)

    def test_clipping_is_warning_and_gain_preserved(self):
        audio = preprocess_audio(self.wav(samples=np.tile([-1., 1., 0.25, -0.25], 2000)))
        self.assertTrue(any('clipping' in warning for warning in audio.warnings))
        self.assertEqual(min(audio.waveform), -1.)
        self.assertEqual(audio.waveform[2], 0.25)

    def test_stereo_cancellation_does_not_become_fake_signal(self):
        samples = np.tile([[1., -1.]], (8000, 1))
        self.assert_error('silent_audio', lambda: preprocess_audio(self.wav(channels=2, width=4, samples=samples)))

    def test_resampling_suppresses_aliases(self):
        # Keep a 1 kHz passband tone so the stopband test stays above the silence floor.
        time = np.arange(48000) / 48000
        low = 0.1 * np.sin(2*np.pi*1000*time)
        mixed = low + 0.4 * np.sin(2*np.pi*12000*time)
        reference = np.array(preprocess_audio(self.wav(rate=48000, width=4, samples=low)).waveform)
        output = np.array(preprocess_audio(self.wav(rate=48000, width=4, samples=mixed)).waveform)
        error_rms = np.sqrt(np.mean((output[200:-200] - reference[200:-200])**2))
        self.assertLess(error_rms, 0.001)  # >49 dB suppression relative to 0.4 sine RMS.
        self.assertAlmostEqual(np.sqrt(np.mean(reference[200:-200]**2)), 0.1/np.sqrt(2), delta=0.001)

    def test_resampling_overshoot_is_bounded_and_reported(self):
        square = np.where(np.arange(24000) % 480 < 240, 0.9999, -0.9999)
        audio = preprocess_audio(self.wav(rate=48000, width=4, samples=square))
        self.assertTrue(np.isfinite(audio.waveform).all())
        self.assertLessEqual(max(map(abs, audio.waveform)), 1)
        self.assertTrue(any('overshoot' in warning for warning in audio.warnings))

    def test_fractional_resampling_length(self):
        audio = preprocess_audio(self.wav(rate=44100, duration=0.5001))
        self.assertEqual(len(audio.waveform), round(round(44100*0.5001) * 16000/44100))

    def test_invalid_target_rates(self):
        for rate in (True, 0, 7999, 48001, 16000., None):
            self.assert_error('invalid_configuration', lambda: preprocess_audio(self.wav(), target_sample_rate=rate))

    def test_bad_header_fields_and_alignment(self):
        path = self.wav()
        original = path.read_bytes()
        for offset, fmt, value, code in ((4, '<I', 1, 'invalid_audio'),
                (24, '<I', 0, 'invalid_audio'), (28, '<I', 1, 'invalid_audio'),
                (32, '<H', 1, 'invalid_audio'), (40, '<I', 15999, 'invalid_audio'),
                (20, '<H', 3, 'unsupported_audio'), (20, '<H', 6, 'unsupported_audio'),
                (22, '<H', 3, 'unsupported_audio'), (34, '<H', 12, 'unsupported_audio'),
                (24, '<I', 7999, 'unsupported_audio'), (24, '<I', 192001, 'unsupported_audio')):
            with self.subTest(offset=offset, value=value):
                changed = bytearray(original)
                struct.pack_into(fmt, changed, offset, value)
                path.write_bytes(changed)
                self.assert_error(code, lambda: preprocess_audio(path))

    def test_truncated_wrong_and_unsupported_containers(self):
        path = self.wav()
        original = path.read_bytes()
        for content, code in ((b'', 'invalid_audio'), (b'not wave data', 'invalid_audio'),
                (original[:-1], 'invalid_audio'), (original+b'extra', 'invalid_audio'),
                (b'RIFX'+original[4:], 'unsupported_audio'),
                (b'RF64'+original[4:], 'unsupported_audio'),
                (b'RIFF'+original[4:8]+b'NOPE'+original[12:], 'invalid_audio')):
            path.write_bytes(content)
            self.assert_error(code, lambda: preprocess_audio(path))
        unsupported = self.folder / 'synthetic.mp3'
        unsupported.write_bytes(original)
        self.assert_error('unsupported_audio', lambda: preprocess_audio(unsupported))
        self.assert_error('invalid_audio', lambda: preprocess_audio(self.folder))

    def test_chunk_bounds_duplicates_missing_and_metadata(self):
        path = self.wav()
        original = path.read_bytes()
        fmt_chunk, data_chunk = original[12:36], original[36:]
        def container(chunks):
            body = b'WAVE' + chunks
            path.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)
        for chunks in (fmt_chunk, data_chunk, fmt_chunk*2+data_chunk,
                       fmt_chunk+data_chunk*2, fmt_chunk+data_chunk+b'x',
                       fmt_chunk+b'JUNK'+struct.pack('<I', 99999999)):
            container(chunks)
            self.assert_error('invalid_audio', lambda: preprocess_audio(path))
        container(fmt_chunk+b'JUNK'+struct.pack('<I', 3)+b'abc\0'+data_chunk)
        self.assertEqual(preprocess_audio(path).duration_s, 0.5)
        # Final odd-length PCM8 data with no pad is emitted by Python's wave writer.
        self.assertEqual(len(preprocess_audio(self.wav(width=1, duration=8001/16000)).waveform), 8001)

    def test_extensible_pcm_and_invalid_extension(self):
        path = self.wav()
        original = path.read_bytes()
        extension = struct.pack('<HHI', 22, 16, 0) + bytes.fromhex('0100000000001000800000aa00389b71')
        fmt = bytearray(original[20:36] + extension)
        struct.pack_into('<H', fmt, 0, 0xFFFE)
        def save(value):
            body = b'WAVEfmt ' + struct.pack('<I', len(value)) + value + original[36:]
            path.write_bytes(b'RIFF' + struct.pack('<I', len(body)) + body)
        save(fmt)
        self.assertEqual(preprocess_audio(path).duration_s, 0.5)
        for offset, value, code in ((16, 30, 'invalid_audio'), (16, 0, 'invalid_audio'),
                                     (18, 12, 'unsupported_audio'), (24, 3, 'unsupported_audio')):
            changed = bytearray(fmt)
            struct.pack_into('<H', changed, offset, value)
            save(changed)
            self.assert_error(code, lambda: preprocess_audio(path))
