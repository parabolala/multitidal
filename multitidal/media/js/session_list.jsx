class SessionsList extends React.Component {
    constructor(props) {
        super(props);
        this.state = {sessions: []};
        this.ws = null;
    }

    componentDidMount() {
        this.ws = new WebSocket(
            "ws://localhost:3000/watch_list");
        // Connection opened
        this.ws.addEventListener('open', function (event) {
            console.log('opened');
        });
        
        // Listen for messages
        var that = this;
        this.ws.addEventListener('message', function (event) {
            var json = JSON.parse(event.data)
            that.onMessage(json);
        });
    }

    componentWillUnmount(){
        this.ws.close();
        this.ws = null;
    }

    onMessage(message) {
        console.log(message);
        
        if (message.command === "session_add") {
            var newSessions = this.state.sessions.slice(0);
            newSessions.push(
                             {
                                 id: message.session_id,
                                 state: 0,
                                 timeout: null
                             });
            this.setState({
                sessions: newSessions
            });
        } else if (message.command === "session_remove") {
            var newSessions = this.state.sessions.filter((session) => 
                session.id !== message.session_id);
            this.setState({
                sessions: newSessions
            });
        } else if (message.command === "keystrokes") {
            const s_id = message.keystrokes.session_id;
            this.activateSession(s_id);
        }
    }

  activateSession(session_id) {
      var that = this;
      var newSessions = this.state.sessions.map(function(session) {
          var newSession = session;
          if (session.id === session_id) {
              newSession = Object.assign({}, session);
              if (session.state === 0) {
                  newSession.state = 1;
              } else {
                  clearTimeout(session.timeout);
              }
              newSession.timeout = setTimeout(
                  () => that.deactivateSession(session_id),
                  100);
          }
          return newSession;
      });
      console.log("SetState in act");
      this.setState({"sessions": newSessions});
  }

  deactivateSession(session_id) {
      var newSessions = this.state.sessions.map(function(session) {
          var newSession = session;
          if (session.id === session_id) {
              newSession = Object.assign({}, session);
              if (session.state === 1) {
                  newSession.state = 0;
              } 
              clearTimeout(session.timeout);
              newSession.timeout = null;
          }
          return newSession;
      });
      console.log("SetState in deact");
      this.setState({"sessions": newSessions});
  }

  onSessionClick(session) {
      console.log("Clicked");
      this.props.onSessionChosen(session.id);
  }

  render() {
    var listItems;
    var that = this;
    if (this.state.sessions.length > 0) {
      console.log("Rendering sessions: ");
      console.log(this.state.sessions[0].state);
      }
    if (this.state.sessions.length === 0) {
      listItems = <li> no session </li>;
    } else {
        listItems = this.state.sessions.map(function(session) { 
          let className = "session";
          if (session.state === 1) {
              className += " keystrokes";
          }
          return <li key={session.id} className={className} onClick={(e) => that.onSessionClick(session)}>session: {session.id}, state: {session.state}</li>
        });
    }

    return (
      <div className="shopping-list">
        <h1>Sessions List </h1>
        <ul>
            {listItems}
        </ul>
      </div>
    );
  }
}

class Main extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            session_id: null
        };
    }

    observeSession(session_id) {
        console.log("About to observe session " + session_id);
        this.setState({
            session_id: session_id
        });
    }

    cancelObservation() {
        this.observeSession(null);
    }

    render(){ 
        if (this.state.session_id === null) {
            return <SessionsList onSessionChosen={this.observeSession.bind(this)} />;
        }
        return (
            <div>
                <a href="#" onClick={this.cancelObservation.bind(this)}>Cancel</a>,
                <Observation session_id={this.state.session_id} />
            </div>
        );
    }   
}

class SSHFrame extends React.Component {
    constructor(props) {
        super(props);
        this.frame = React.createRef();
    }
    
    componentDidMount() {
      this.frame.addEventListener("load", this.handleIframeLoad); 
        // Somehow iframe doesn't load at first. Reset src= afte 1s.
      // window.setTimeout(
      //   (function(){ this.frame.src = this.props.src;}).bind(this),
      //   2000);
    }
    componentWillUnmount() {
      this.frame.removeEventListener("load", this.handleIframeLoad);
    }
    handleIframeLoad = (event) => {
      console.log('Iframe content has been loaded :)');
    }
    
    render() {  
      console.log('rendering iframe');
      return(
          <div className="ssh">
            <iframe 
              src={this.props.src}
              className="ssh-frame"
              ref={ frame => this.frame = frame }
            />
          </div>
      );
    }  
}

class MP3Player extends React.Component {
    constructor(props) {
        super(props);
    }

    render() {
        return (
           <audio autoPlay src={this.props.src}></audio>
        );
    }
}

class Observation extends React.Component {
    constructor(props) {
        super(props);
        this.ws = null;
        this.state = {
            ssh_url: null,
            mp3_url: null
        };
    }

    componentDidMount() {
        this.ws = new WebSocket("ws://localhost:3000/observe/" + this.props.session_id);
        // Connection opened
        this.ws.addEventListener('open', function (event) {
            console.log('opened');
        });
        
        // Listen for messages
        var that = this;
        this.ws.addEventListener('message', function (event) {
            var json = JSON.parse(event.data)
            that.onMessage(json);
        });
    }

    componentWillUnmount(){
        this.ws.close();
        this.ws = null;
    }

    onMessage(data) {
        console.log("Got message");
        console.log(data);
        if (data.status === 'connected') {
            this.setState({
                ssh_url: data.ssh.url,
                mp3_url: data.mp3.url
            });
        }
    }

    render() {
        if (!this.state.ssh_url) {
            return '';
        }
        return (
                <div className="observation">
                  <MP3Player src={this.state.mp3_url} />
                  <SSHFrame src={this.state.ssh_url} />
                </div>
        );
    }
}





const domContainer = document.querySelector('#sessions-list-container');
ReactDOM.render(<Main />, domContainer);
