import json

TASK_NAME = 'notebook_dist'

data = {}
with open(f'{TASK_NAME}.ipynb', 'r') as f:
	data = json.load(f)

SECTION_START_KEYS = {
	'intro_start' : 'intro',
    'tutorial_start' : 'tutorial',
    'null_clean_start' : 'null_clean',
    'model_start' : 'model',
    'end_start' : 'end'
}


current_section = SECTION_START_KEYS['intro_start']

for cell in data['cells']:
    if cell['cell_type'] == 'markdown':
        cell['metadata'].update({'trusted':True,
                            'editable': False,
                            'deletable': False})
    if cell["cell_type"] == "code":
        cell["outputs"] = []
        cell["execution_count"] = None
    if cell['metadata'].get("new_section"):
        current_section = SECTION_START_KEYS[cell['metadata']["new_section"]]
    cell['metadata']['section'] = current_section

with open(f'{TASK_NAME}_build.ipynb', 'w') as f:
	json.dump(data, f, indent = 1)

print(f'Built task in: {TASK_NAME}_build.ipynb')
