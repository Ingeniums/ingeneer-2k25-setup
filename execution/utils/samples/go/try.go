package main

import (
	"fmt"
	"strings"
)

func main() {
	input := `{{INPUT}}`
	input = strings.TrimSpace(input)
	fmt.Println(strings.ToUpper(input))
}
