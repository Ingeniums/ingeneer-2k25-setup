package main

import (
	"fmt"
	"os"
)

var input string = "{{INPUT}}"

func main() {
    dat, err := os.ReadFile("./input.txt")
    if err != nil {
        panic(err)
    }

    fmt.Print(string(dat))
}
