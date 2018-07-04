#!/bin/bash
printf 'Message-Authenticator = 0x00' |radclient 127.0.0.1 status 5e588ba494f86ad0bddf9e2fe4cf4d64 || exit 1
exit 0
