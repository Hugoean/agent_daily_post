#!/bin/bash

echo "🚀 Starting..."

if [ ! -f .env ]; then
  echo "❌ 请先复制 .env.example 为 .env"
  exit 1
fi

export $(grep -v '^#' .env | xargs)

pip install -r requirements.txt

python fetch_and_send.py