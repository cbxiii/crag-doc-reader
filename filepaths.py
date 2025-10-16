"""
Script that gets filepaths for each PDF and creates
a txt file for all of them.
"""

from glob import glob

filepaths = glob('./documents/*')

with open('filepaths.txt', 'w') as f:
    for i in range(len(filepaths)):
        f.write(f"{filepaths[i]}\n")