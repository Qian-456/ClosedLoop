import re
path = 'backend/src/scripts/mock_data/generator.py'
content = open(path, encoding='utf-8').read()
content = re.sub(r'start_time=_start_time\(\),?', 'start_time="AUTO",', content)
open(path, 'w', encoding='utf-8').write(content)
