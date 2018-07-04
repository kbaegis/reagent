/*

podTemplate(label: 'oci-build', containers: [
    containerTemplate(name: 'oci-build', nodeSelector: "type=server,zone=b", image: 'crucible.lab:4000/oci/build:latest', ttyEnabled: true, privileged: true, alwaysPullImage: true, command: 'bash')
]) {

    node('oci-build') {
        stage('Run entrypoint') {
            container('oci-build') {
                sh 'sudo GOPATH=/root/.go/ TERM=xterm /usr/local/bin/entrypoint.sh -d'
            }
        }
        stage('Build catalyst') {
            container('oci-build') {
                sh 'sudo TERM=xterm /usr/local/bin/build -p -c'
            }
        }
        stage('Build initial') {
            container('oci-build') {
                sh 'sudo TERM=xterm /usr/local/bin/build -i'
            }
        }
        stage('Build projects') {
            container('oci-build') {
                sh 'sudo TERM=xterm /usr/local/bin/build -b all'
            }
        }
    }
}
*/

pipeline {
    agent {
        kubernetes {
            label 'oci-build'
            defaultContainer 'jnlp'
            yaml """
apiVersion: v1
kind: Pod
metadata:
  name: oci-build
  labels:
    label: oci-build
spec:
  nodeSelector:
    type: server
    zone: b
  nodeName: crucible
  containers:
  - name: oci-build
    image: crucible.lab:4000/oci/build:latest
    command:
    - bash
    tty: true
    securityContext:
      privileged: true
    imagePullPolicy: Always
"""
        }
    }
    stages {
        stage('Run entrypoint') {
            steps {
                container('oci-build') {
                    sh 'sudo GOPATH=/root/.go/ TERM=xterm /usr/local/bin/entrypoint.sh -d'
                }
            }
        }
        stage('Build catalyst') {
            steps {
                container('oci-build') {
                    sh 'sudo TERM=xterm /usr/local/bin/build -p -c'
                }
            }
        }
        stage('Build initial') {
            steps {
                container('oci-build') {
                    sh 'sudo TERM=xterm /usr/local/bin/build -i'
                }
            }
        }
        stage('Build projects') {
            steps {
                container('oci-build') {
                    sh 'sudo TERM=xterm /usr/local/bin/build -b all'
                }
            }
        }
    }
}
