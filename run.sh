#!/bin/bash
command_name="docsify"

if which $command_name &> /dev/null
then
    echo "docsify has been installed!"
else
    echo "docsify not found, please install docsify by `npm install docsify-cli -g`"
    exit 1
fi

docsify serve . 