import json
import re


sections_dict = {}


def build_sections_dictionary():
    #regex expression for getting markdown comments
    is_comment = re.compile('<!---(.+)-->')
    section_key = None
    current_section = []
    with open('notebook_dist.md', 'r') as f:
        lines = f.readlines()
        for line in lines:
            candidate_match = is_comment.match(line)
            if candidate_match:
                #current section array gets added to sectiosn dictionary
                if section_key:
                    sections_dict[section_key] = current_section
                    current_section = []
                #get new section key
                section_key = candidate_match.group(1).strip().lower()
                print(section_key)
                continue
            elif section_key:
                current_section.append(line)
        #add the last section if it was missed in the loop
        if current_section and section_key:
            sections_dict[section_key] = current_section
    return sections_dict

def build_notebook_dist_from_keys_in(sections_dict):
    with open('notebook_dist.tmpl', 'r') as f_r:
        lines = f_r.readlines()
        with open('notebook_dist_build.ipynb', 'w') as f_w:
            for line in lines:
                #print(line.strip().lower())
                candidate_replace = line.strip().lower()

                did_write_in_loop = False
                for k, v in sections_dict.items():
                    if k in candidate_replace:
                    	#major hack, making all lines be in double quotes
                    	#by inserving a single quote into all lines
                        v = [s.replace('"','!@!@!')+"~~'~~" for s in v]
                        #the key with the list and add line back in
                        v = str(v).replace('\\n', '\\\\n')
                        #replace single quote with double
                        print(v)
                        v = v.replace("~~'~~",'')
                        v = v.replace('!@!@!', '"')
                        #add a comma at the end to make it valid json
                        #print(v)
                        line = re.sub(f'(?i){k}', v, line)
                        f_w.write(line)
                        did_write_in_loop = True
                        break
                if not did_write_in_loop:
                    f_w.write(line)
    print('build finished')

build_notebook_dist_from_keys_in(build_sections_dictionary())

