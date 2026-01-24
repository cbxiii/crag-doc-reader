import subprocess
from pathlib import Path


def main():
    paths_file = Path("all_filepaths.txt")
    if not paths_file.exists():
        print("all_filepaths.txt not found")
        return

    with paths_file.open('r', encoding='utf-8') as f:
        for line in f:
            path = line.strip()
            if not path:
                continue
            print(f"Processing: {path}")
            try:
                subprocess.run(["python3", "add_to_vector_store.py", path], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Error processing {path}: {e}")
            except KeyboardInterrupt:
                print("Interrupted by user")
                return


if __name__ == '__main__':
    main()