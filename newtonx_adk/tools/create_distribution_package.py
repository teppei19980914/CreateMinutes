import os
import shutil
import glob
from pathlib import Path
import sys

def create_distribution_package():
    """
    配布用パッケージ(zip)を作成するスクリプト
    
    構成:
    newtonx_adk/
      ├── newtonx_adk-*.whl
      ├── docs/
      │   ├── adk/
      │   ├── newtonx_adk_knowledge.md
      │   └── auth_setup_guide.md
      ├── tools/
      ├── skills/
      │   └── newtonx-adk/
      └── adk_examples/
    """
    # プロジェクトルートの特定（このスクリプトは tools/ にあると仮定）
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    dist_dir = project_root / "dist"
    
    print(f"Project root: {project_root}")
    print(f"Dist dir: {dist_dir}")

    if not dist_dir.exists():
        print("Error: dist directory does not exist. Please run build first.")
        sys.exit(1)

    # 出力設定
    output_zip_base = "newtonx_adk"
    temp_dir = dist_dir / "newtonx_adk_tmp"
    package_root = temp_dir / "newtonx_adk"
    
    # クリーンアップ（既存の一時フォルダがあれば削除）
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    
    try:
        package_root.mkdir(parents=True)
        print(f"Created temp directory: {package_root}")

        # 1. whlファイルの特定とコピー
        # dist直下のwhlファイルを探す
        whl_files = list(dist_dir.glob("newtonx_adk-*-py3-none-any.whl"))
        if not whl_files:
            print("Error: .whl file not found in dist directory.")
            sys.exit(1)
        
        # 最新のものを選択（更新日時順）
        latest_whl = max(whl_files, key=os.path.getmtime)
        print(f"Copying whl: {latest_whl.name}")
        shutil.copy2(latest_whl, package_root / latest_whl.name)

        # 2. docsのコピー
        print("Copying docs...")
        docs_dest = package_root / "docs"
        docs_dest.mkdir()
        
        # docs/adk
        adk_docs_src = project_root / "docs" / "adk"
        if adk_docs_src.exists():
            shutil.copytree(adk_docs_src, docs_dest / "adk")
        
        # docs/*.md
        for filename in ["newtonx_adk_knowledge.md", "auth_setup_guide.md"]:
            src_file = project_root / "docs" / filename
            if src_file.exists():
                shutil.copy2(src_file, docs_dest / filename)
            else:
                print(f"Warning: {filename} not found.")

        # 共通の除外パターン関数
        def ignore_patterns(path, names):
            return [n for n in names if n == "__pycache__" or n == ".DS_Store"]

        # 3. toolsのコピー
        print("Copying tools...")
        tools_src = project_root / "tools"
        shutil.copytree(tools_src, package_root / "tools", ignore=ignore_patterns)

        # 4. skillsのコピー
        print("Copying skills...")
        skills_src = project_root / ".cursor" / "skills" / "newtonx-adk"
        skills_dest = package_root / "skills" / "newtonx-adk"
        
        if skills_src.exists():
            skills_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skills_src, skills_dest)
        else:
            print("Warning: Skills directory not found.")

        # 5. adk_examplesのコピー
        print("Copying adk_examples...")
        examples_src = project_root / "adk_examples"
        
        if examples_src.exists():
            shutil.copytree(examples_src, package_root / "adk_examples", ignore=ignore_patterns)
        else:
            print("Warning: adk_examples directory not found.")

        # 6. Zip化
        output_zip_path = dist_dir / output_zip_base
        print(f"Creating zip archive: {output_zip_path}.zip")
        shutil.make_archive(str(output_zip_path), 'zip', root_dir=temp_dir)
        
        print("Done.")

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        # クリーンアップ
        if temp_dir.exists():
            print("Cleaning up temp directory...")
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    create_distribution_package()
