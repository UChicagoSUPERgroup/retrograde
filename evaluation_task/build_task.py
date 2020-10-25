import json

TASK_NAME = 'notebook_dist'

data = {}
with open(f'{TASK_NAME}.ipynb', 'r') as f:
	data = json.load(f)

for cell in data['cells']:
	if cell['cell_type'] == 'markdown':
		cell['metadata'] = {'trusted':True,
		                    'editable': False,
		                    'deletable': False}

with open(f'{TASK_NAME}_build.ipynb', 'w') as f:
	json.dump(data, f)

print(f'Built task in: {TASK_NAME}_build.ipynb')