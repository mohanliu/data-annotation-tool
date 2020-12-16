#!/bin/bash
app="rd_data_tool"
port="7000"
docker build -t ${app} .
docker rm -f $app
docker run -d -p $port:80 \
  --name=${app} \
  -v $PWD:/app -v /beegfs-lab:/beegfs-lab \
  -v /data-non-pii-share:/data-non-pii-share ${app}
