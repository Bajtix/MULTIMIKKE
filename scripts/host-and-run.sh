#!/bin/bash
./send-notif-ip.sh &
echo "EVIta_12PI" | sudo -S create_ap -n wlo1 "byliście na otwarciu?" nfkfnfkfnfkf & ./run.sh
echo "Cleaning up"
echo "EVIta_12PI" | sudo -S create_ap --stop wlo1
