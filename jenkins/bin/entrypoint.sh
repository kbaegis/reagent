#!/bin/bash

su jenkins -c '/usr/lib64/icedtea8/bin/java -Djava.awt.headless=true -DJENKINS_HOME="/var/lib/jenkins/home" -jar /opt/jenkins/jenkins.war --prefix=/jenkins'
