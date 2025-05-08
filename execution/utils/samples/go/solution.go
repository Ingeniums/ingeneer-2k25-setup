package main

import (
	"fmt"
	"log"
	"os"
	"strings"
)

func main() {
	data, err := os.ReadFile("/home/merzouka/code/inge/neer/setup/execution/utils/samples/input.txt")
	
	if err != nil {
		log.Fatal(err)
		return
	}
	
	text := string(data)
	text = strings.TrimSpace(text)
	text = strings.ToUpper(text)
	
	fmt.Println(text)
}
