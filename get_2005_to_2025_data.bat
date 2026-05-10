if not exist data mkdir data

echo Downloading danbooru_clean.parquet...
curl -L "https://huggingface.co/datasets/ThetaCursed/danbooru-2026-clean-metadata/resolve/main/danbooru2026_clean.parquet?download=true" -o data/danbooru2026_clean.parquet
