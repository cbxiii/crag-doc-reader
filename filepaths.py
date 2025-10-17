"""
Script that gets the paths of all the research paper files and stores it
in a txt file.
"""

from glob import glob

filepaths = glob('./documents/*')

with open('filepaths.txt', 'w') as f:
    for path in filepaths:
        f.write(f"{path}\n")