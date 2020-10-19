#! /bin/bash

echo -e "\e[1;31m 1. 启动后台定时任务 \e[0m"
python /server/main.py scheduler > /dev/null 2>&1 &

echo -e "\e[1;31m 2. 启动服务 \e[0m"
python3 /server/main.py
