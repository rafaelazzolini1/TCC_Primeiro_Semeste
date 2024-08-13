import { useState } from 'react';
import APIService from '../Components/APIService'

const Form = (props) => {

  return (
       <div>
        <form>
            <input type="text" value={content} onChange={e => setContent(e.target.value)} />
            <button type="submit" value="Enviar Texto" onClick= {async () => {
            const text = { content };
            const response = await fetch("/add", {
            method: "POST",
            headers: {
            'Content-Type' : 'application/json'
            },
            body: JSON.stringify(text)
            })
            if (response.ok){
            console.log("it worked")
            }}}>
            </button>
            </form>
       </div>
  )}

export default Form;