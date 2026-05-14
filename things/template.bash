#!/usr/bin/env bash
set -euo pipefail

name="$0"
part=""
template="cad"

usage() {
  cat <<EOF

SCAD Part generator

usage:
  $name PART [--template TEMPLATE]

examples:
  $name pump_bracket
  $name access_cover --template cover

EOF
}

list_templates() {
  local template_dir="./3d_template/scad"
  local template_file
  if [[ -d "$template_dir" ]]; then
    for template_file in "$template_dir"/*.scad; do
      [[ -e "$template_file" ]] || continue
      printf '  %s\n' "$(basename "$template_file" .scad)"
    done | sort
  fi
  [[ -f ./3d_template/cad.scad ]] && printf '  cad\n'
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --template)
      [[ "$#" -ge 2 ]] || {
        echo "--template requires a value" >&2
        exit 2
      }
      template="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      if [[ -n "$part" ]]; then
        echo "Unexpected argument: $1" >&2
        usage >&2
        exit 2
      fi
      part="$1"
      shift
      ;;
  esac
done

if [[ -z "$part" ]]; then
  usage >&2
  exit 2
fi

if [[ ! "$part" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Part name must use only letters, digits, underscore, or hyphen: $part" >&2
  exit 2
fi

if [[ ! "$template" =~ ^[A-Za-z0-9_-]+$ ]]; then
  echo "Template name must use only letters, digits, underscore, or hyphen: $template" >&2
  exit 2
fi

template_path="./3d_template/scad/${template}.scad"
if [[ "$template" == "cad" && ! -f "$template_path" ]]; then
  template_path="./3d_template/cad.scad"
fi

if [[ ! -f "$template_path" ]]; then
  echo "Unknown template: $template" >&2
  echo "Available templates:" >&2
  list_templates >&2
  exit 1
fi

if [[ -e "$part" ]]; then
  echo "Part already exists: $part" >&2
  exit 1
fi

echo "Creating new OpenSCAD part: $part"
echo "Template: $template"

mkdir "$part"
cp ./3d_template/generate.bash "./$part/generate.bash"
cp "$template_path" "./$part/$part.scad"
sed -i -e "s/__cad__name__/$part/g" "./$part/generate.bash"
rm -f "./$part/generate.bash-e"
