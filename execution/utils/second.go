package main

import (
	"fmt"
	"os"
	"strings"
)

func main() {
    dat, err := os.ReadFile("./input.txt")
    if err != nil {
        panic(err)
    }
    var i int; for i = 0; i < 10000000; i++ {}
    fmt.Println(i)
    fmt.Println(strings.TrimSpace(string(dat))) 
}
