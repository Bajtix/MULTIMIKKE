#!/bin/bash
sleep 10
var=$(ip address | grep -zoP 'ap0:[\s\S]+inet \K\S+(?=\/)' | tr -d '\0')
echo "Ip address is: $var"
notify-send "RUNNING HOTSPOT AT $var" -t 20000
