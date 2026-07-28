from pathlib import Path
from audio.loader import load_audio
from audio.writer import write_wav
import numpy as np

# Create dummy noise
noise = np.random.uniform(-0.1, 0.1, (44100 * 5, 2)).astype(np.float32)
write_wav(Path("dummy.wav"), noise, 44100)

from ai.bs_roformer import BSRoFormerModel
model = BSRoFormerModel(chunk_size=35840)
model.load(Path("models"))
print("Model loaded.")
stems = model.separate(Path("dummy.wav"), Path("dummy_out"))
print("Stems:")
for k, v in stems.items():
    data, _ = load_audio(v)
    print(k, data.shape, np.max(data), np.min(data), np.mean(np.abs(data)))
