#!/bin/bash
true && sudo bash -c "python -m lcrs.master.main $@ 2>&1 | tee -a /var/log/lcrs.error.log"
