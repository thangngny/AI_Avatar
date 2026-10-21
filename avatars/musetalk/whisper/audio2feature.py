import os
from .whisper import load_model
import soundfile as sf
import numpy as np
import time
import sys
from transformers import AutoFeatureExtractor
from transformers import WhisperModel
import torch
sys.path.append("..")

_default_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_default_weight_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
class Audio2Feature():
    def __init__(self,
                 whisper_model_type="tiny",
                 model_path="./models/whisper",
                 device=None):
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(model_path)
        self.whisper = WhisperModel.from_pretrained(model_path)
        self.device = device if device is not None else _default_device
        # CPU must use float32; GPU can use float16
        self.weight_dtype = torch.float32 if self.device.type == "cpu" else _default_weight_dtype
        self.whisper = self.whisper.to(device=self.device, dtype=self.weight_dtype).eval()
        self.whisper.requires_grad_(False)

    def get_sliced_feature(self,
                           feature_array, 
                           vid_idx, 
                           audio_feat_length=[2,2],
                           fps=25):
        """
        Get sliced features based on a given index
        :param feature_array: 
        :param start_idx: the start index of the feature
        :param audio_feat_length:
        :return: 
        """
        length = len(feature_array)
        selected_feature = []
        selected_idx = []
        
        center_idx = int(vid_idx*50/fps) 
        left_idx = center_idx; #-audio_feat_length[0]*2
        right_idx = center_idx + (audio_feat_length[0]+audio_feat_length[1]+1)*2
        
        for idx in range(left_idx,right_idx):
            idx = max(0, idx)
            idx = min(length-1, idx)
            x = feature_array[idx]
            selected_feature.append(x)
            selected_idx.append(idx)
        
        selected_feature = np.concatenate(selected_feature, axis=0)
        selected_feature = selected_feature.reshape(-1, 384)# 50*384
        return selected_feature,selected_idx

    def get_sliced_feature_sparse(self,feature_array, vid_idx, audio_feat_length= [2,2],fps = 25):
        """
        Get sliced features based on a given index
        :param feature_array: 
        :param start_idx: the start index of the feature
        :param audio_feat_length:
        :return: 
        """
        length = len(feature_array)
        selected_feature = []
        selected_idx = []

        for dt in range(-audio_feat_length[0],audio_feat_length[1]+1):
            left_idx = int((vid_idx+dt)*50/fps)
            if left_idx<1 or left_idx>length-1:
                print('test-----,left_idx=',left_idx)
                left_idx = max(0, left_idx)
                left_idx = min(length-1, left_idx)

                x = feature_array[left_idx]
                x = x[np.newaxis,:,:]
                x = np.repeat(x, 2, axis=0)
                selected_feature.append(x)
                selected_idx.append(left_idx)
                selected_idx.append(left_idx)
            else:
                x = feature_array[left_idx-1:left_idx+1]
                selected_feature.append(x)
                selected_idx.append(left_idx-1)
                selected_idx.append(left_idx)
        selected_feature = np.concatenate(selected_feature, axis=0)
        selected_feature = selected_feature.reshape(-1, 384)# 50*384
        return selected_feature,selected_idx
    

    def feature2chunks(self,feature_array,fps,batch_size,audio_feat_length = [2,2],start=0):
        whisper_chunks = []
        whisper_idx_multiplier = 50./fps 
        i = 0
        #print(f"video in {fps} FPS, audio idx in 50FPS")
        for _ in range(batch_size):
            # start_idx = int(i * whisper_idx_multiplier)
            # if start_idx>=len(feature_array):
            #     break
            selected_feature,selected_idx = self.get_sliced_feature(feature_array= feature_array,vid_idx = i+start,audio_feat_length=audio_feat_length,fps=fps)
            #print(f"i:{i},selected_idx {selected_idx}")
            whisper_chunks.append(selected_feature)
            i += 1
        return whisper_chunks
    
    def audio2feat(self, wav_data): #, weight_dtype=None
        # Long-audio safe extraction.
        #
        # The HuggingFace WhisperFeatureExtractor is configured with
        # chunk_length=30 / n_samples=480000, so a SINGLE call truncates any input
        # longer than 30 s to the first 30 s and emits exactly 1500 encoder
        # features. Feeding a 167 s waveform in one call therefore returned 1500
        # features (covering only 0-30 s) and the renderer's index clamp silently
        # reused the final feature for every frame past 30 s -> mouth froze while
        # the muxed audio kept playing (see SYSTEM_LIPSYNC_DIAGNOSIS.md, P0).
        #
        # Fix: if the waveform is longer than the Whisper window, split it into
        # 30 s segments by exact sample index, encode each segment, trim each
        # segment's features to its REAL temporal length (discarding the
        # zero-padded tail), and concatenate along the TIME axis (axis 0). The
        # result is one continuous [T, 5, 384] array covering the full duration.
        #
        # Short audio (<= 30 s) keeps the original single-call behavior so the
        # realtime pipeline (which feeds small sliding windows) is unchanged.
        wav = np.asarray(wav_data, dtype=np.float32).reshape(-1)
        n_samples_max = int(getattr(self.feature_extractor, "n_samples", 480000))
        if wav.shape[0] <= n_samples_max:
            return self._encode_block(wav)
        return self._audio2feat_long(wav)

    def _valid_feat_count(self, n_samples: int) -> int:
        # Real number of encoder features produced by `n_samples` PCM samples.
        # The extractor builds mel frames at hop_length (160 samples/frame) and
        # caps at nb_max_frames = n_samples_max // hop_length (3000). The encoder
        # downsamples by 2, so valid_features = mel_frames // 2.
        hop = int(getattr(self.feature_extractor, "hop_length", 160))
        max_mel = int(getattr(self.feature_extractor, "n_samples", 480000)) // hop
        mel_frames = n_samples // hop + 1
        return min(mel_frames, max_mel) // 2

    def _encode_block(self, wav: np.ndarray) -> np.ndarray:
        # Encode one <= 30 s block. Returns [1500, 5, 384] (padded to the full
        # Whisper window) — identical to the original audio2feat output contract.
        input_feature = self.feature_extractor(
            wav,
            return_tensors="pt",
            sampling_rate=16000
        ).input_features
        input_feature = input_feature.to(self.device).to(self.weight_dtype)
        with torch.no_grad():
            whisper_feature = self.whisper.encoder(input_feature, output_hidden_states=True).hidden_states
        whisper_feature = torch.stack(whisper_feature, dim=2)
        return whisper_feature.squeeze(0).cpu().numpy()

    def _audio2feat_long(self, wav: np.ndarray) -> np.ndarray:
        # Chunked extraction for audio > 30 s with windowed-overlap-and-add
        # (WOLA) to avoid 30 s chunk-boundary discontinuities.
        #
        # Each 30 s window is encoded independently by the Whisper encoder, so
        # the mel/encoder context resets at every chunk boundary. Concatenating
        # the raw segments produces a ~6x feature step at each boundary
        # (measured: step 105 vs median 16) plus an outlier last-feature per
        # segment -> a visible mouth glitch every 30 s. WOLA fixes this: windows
        # overlap by `overlap_sec` and are blended with a linear crossfade so the
        # boundary falls inside a blended region instead of at a hard seam.
        #
        # Sample-based geometry (no rounding drift): chunk/hop/overlap are all
        # multiples of samples_per_feat (320 @ 50 Hz), so every window's local
        # feature j maps to an integer global feature index a_k + j.
        sr = 16000
        feat_hz = 50.0
        samples_per_feat = int(round(sr / feat_hz))  # 320
        n_max = int(getattr(self.feature_extractor, "n_samples", 480000))  # 480000
        overlap_sec = max(0.0, float(os.getenv("LIVETALKING_WHISPER_CHUNK_OVERLAP_SEC", "1.0")))
        overlap = min(int(overlap_sec * sr), n_max // 2)
        if overlap <= 0:
            # No overlap: legacy concatenation (kept as a fallback; will have
            # boundary discontinuities).
            hop = n_max
        else:
            hop = n_max - overlap
            # keep hop a multiple of samples_per_feat for integer feature mapping
            hop = (hop // samples_per_feat) * samples_per_feat
            overlap = n_max - hop
        overlap_feats = overlap // samples_per_feat  # e.g. 50 for 1 s
        total = int(wav.shape[0])
        # Total feature count for the FULL audio (no 30 s cap — the cap in
        # _valid_feat_count is per-chunk only). 50 Hz = 1 feature / 320 samples.
        total_feats = int(round(total / samples_per_feat))

        # Build window start offsets (sample indices). Uniform hop; the last
        # window is the first one whose [start, start+n_max) reaches >= total.
        starts = []
        s = 0
        while s < total:
            starts.append(s)
            if s + n_max >= total:
                break
            s += hop
        n_win = len(starts)

        out = np.zeros((total_feats, 5, 384), dtype=np.float32)
        wsum = np.zeros((total_feats,), dtype=np.float32)

        for k, start in enumerate(starts):
            end = min(start + n_max, total)
            block = wav[start:end]
            feat = self._encode_block(block)  # [1500, 5, 384] (padded to 30 s)
            n_local = feat.shape[0]
            a_k = start // samples_per_feat  # integer global feature start
            is_first = (k == 0)
            is_last = (k == n_win - 1)
            for j in range(n_local):
                g = a_k + j
                if g >= total_feats:
                    break
                if overlap_feats <= 0:
                    w = 1.0
                else:
                    ramp_in = 1.0 if is_first else min(1.0, j / overlap_feats)
                    ramp_out = 1.0 if is_last else min(1.0, (n_local - 1 - j) / overlap_feats)
                    w = min(ramp_in, ramp_out)
                if w <= 0.0:
                    continue
                out[g] += feat[j] * w
                wsum[g] += w
            print(f"[Whisper Long Audio] window {k}: {start/sr:.3f}-{end/sr:.3f}s "
                  f"-> local {n_local} feats, global [{a_k}, {a_k+n_local})", flush=True)

        # Normalize by overlap weights. Any uncovered index (shouldn't happen with
        # full coverage) is left as zeros.
        covered = wsum > 0
        out[covered] /= wsum[covered, None, None]
        n_uncovered = int((~covered).sum())
        print(f"[Whisper Long Audio] total: duration={total/sr:.3f}s samples={total} "
              f"windows={n_win} overlap={overlap/sr:.2f}s features={out.shape[0]} "
              f"coverage={out.shape[0]/feat_hz:.3f}s uncovered={n_uncovered}", flush=True)
        return out

    # def audio2feat(self,audio_path):
    #     # get the sample rate of the audio
    #     result = self.model.transcribe(audio_path)
    #     embed_list = []
    #     for emb in result['segments']:
    #         encoder_embeddings = emb['encoder_embeddings']
    #         encoder_embeddings = encoder_embeddings.transpose(0,2,1,3)
    #         encoder_embeddings = encoder_embeddings.squeeze(0)
    #         start_idx = int(emb['start'])
    #         end_idx = int(emb['end'])
    #         emb_end_idx = int((end_idx - start_idx)/2)
    #         embed_list.append(encoder_embeddings[:emb_end_idx])
    #     concatenated_array = np.concatenate(embed_list, axis=0)
    #     return concatenated_array

if __name__ == "__main__":
    audio_processor = Audio2Feature(model_path="../../models/whisper/whisper_tiny.pt")
    audio_path = "./test.mp3"
    array = audio_processor.audio2feat(audio_path)
    print(array.shape)
    fps = 25
    whisper_idx_multiplier = 50./fps 

    i = 0
    print(f"video in {fps} FPS, audio idx in 50FPS")
    while 1:
        start_idx = int(i * whisper_idx_multiplier)
        selected_feature,selected_idx = audio_processor.get_sliced_feature(feature_array= array,vid_idx = i,audio_feat_length=[2,2],fps=fps)
        print(f"video idx {i},\t audio idx {selected_idx},\t shape {selected_feature.shape}")
        i += 1
        if start_idx>len(array):
            break
