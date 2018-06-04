subarch: amd64
target: stage1
version_stamp: hardened-latest
rel_type: hardened
profile: default/linux/amd64/17.0/hardened
snapshot: latest
source_subpath: hardened/stage3-amd64-hardened-latest
compression_mode: bzip2
decompressor_search_order: tar pixz xz lbzip2 bzip2 gzip
update_seed: yes
update_seed_command: --newuse --update --deep @world
portage_confdir: /etc/catalyst/portage/
#portage_confdir: @REPO_DIR@/releases/weekly/portage/stages
#SEED
#source_subpath: hardened/stage3-amd64-hardened-20180206T214502Z.tar.xz
