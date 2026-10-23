from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from arm_build import build
from runtime import context

ctx = context()
# reqwest uses Windows SChannel. The unused unconditional OpenSSL dependency
# otherwise compiles vendored OpenSSL with Git's incomplete MSYS Perl runtime.
manifest = Path(ctx['source']) / 'Cargo.toml'
text = manifest.read_text()
dependency = 'openssl = { version = "0.10", features = ["vendored"] }'
if text.count(dependency) != 1:
    raise RuntimeError('Unexpected upstream OpenSSL dependency declaration')
text = text.replace(dependency, '')
text += '\n[target.\'cfg(not(windows))\'.dependencies]\n' + dependency + '\n'
manifest.write_text(text, newline='\n')
build(Path(__file__).parent)
