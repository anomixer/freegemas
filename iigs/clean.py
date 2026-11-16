import re

with open('src/main.c', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace includes
code = re.sub(r'#include "apple2e\.h"', '#include "video.h"\n#include "audio.h"\n#include "input.h"\n#include <string.h>\n', code)
code = re.sub(r'#include "sound\.h"\n', '', code)
code = re.sub(r'#include "music\.h"\n', '', code)
code = re.sub(r'#include "mouse\.h"\n', '', code)

# Remove vera_init
code = re.sub(r'static void vera_init\(void\) \{.*?^\}', '', code, flags=re.MULTILINE|re.DOTALL)

# Replace VERA specific writes with comments
code = re.sub(r'VERA\.[a-zA-Z0-9_]+\s*=\s*[^;]+;', '/* VERA write removed */', code)
code = re.sub(r'vram_at\([^)]+\);', '/* vram_at removed */', code)
code = re.sub(r'vram1_at\([^)]+\);', '/* vram1_at removed */', code)

# Replace input
code = re.sub(r'mouse_read\(\);', 'input_update();', code)
code = re.sub(r'mouse_b\s*&\s*1', 'input_is_mouse_down()', code)
code = re.sub(r'mouse_x', 'input_get_mouse_x()', code)
code = re.sub(r'mouse_y', 'input_get_mouse_y()', code)

with open('src/main.c', 'w', encoding='utf-8') as f:
    f.write(code)
