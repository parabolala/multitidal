class SessionsList extends React.Component {
    constructor(props) {
        super(props);
        this.state = {sessions: []};
        this.ws = null;
    }

    componentDidMount() {
        this.ws = new WebSocket(
            "ws://" + window.location.host + "/watch_list");
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
        console.log(this.state.sessions);
        
        if (message.command === "session_add") {
            var newSessions = this.state.sessions.slice(0);
            newSessions.push(
                             {
                                 id: message.session.id,
                                 state: message.session.state,
                                 kb: message.session.kb,
                                 kb_pressed: false,
                                 timeout: null
                             });
            this.setState({
                sessions: newSessions
            });
        } else if (message.command === "session_remove") {
            var newSessions = this.state.sessions.filter((session) => 
                session.id !== message.session.id);
            this.setState({
                sessions: newSessions
            });
        } else if (message.command === "session_state") {
            var newSessions = this.state.sessions.map((session) => 
                (session.id !== message.session.id ? session : message.session)
            );
            this.setState({
                sessions: newSessions
            });
        } else if (message.command === "keystrokes") {
            const s_id = message.keystrokes.session.id;
            this.activateSession(s_id);
        }
    }

  activateSession(session_id) {
      var that = this;
      var newSessions = this.state.sessions.map(function(session) {
          var newSession = session;
          if (session.id === session_id) {
              newSession = Object.assign({}, session);
              if (session.state === "idle" && session.kb_pressed === false) {
                  newSession.kb_pressed = true;
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
              if (session.kb_pressed === true) {
                  newSession.kb_pressed = false;
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
      this.props.onSessionChosen(session);
  }

  render() {
    var that = this;
    if (this.state.sessions.length > 0) {
      console.log("Rendering sessions: ");
      console.log(this.state.sessions[0].state);
    }
    var body, list;
    if (this.state.sessions.length === 0) {
      body = <a href="#" className="list-group-item list-group-item-warning">
               You're the first one here. Start a new playground with a button below.
             </a>;
      list = null;
    } else {
        var listItems = this.state.sessions.map(function(session) { 
          let className = "session list-group-item ";
          if (session.kb_pressed) {
              className += "list-group-item-danger";
          } else {
              switch (session.state) {
                  case "idle":
                      className += "list-group-item-warning";
                      break;
                  case "running":
                  case "starting":
                      className += "list-group-item-info";
                      break;
                  case "stopping":
                      className += "list-group-item-danger";
                      break;
                  default:
                      console.log("No list item class for session in state: " + session.state);
              }
          }
          return <a
                    key={session.id}
                    className={className}
                    onClick={(session.state === "idle" || session.state === "running" ? 
                              (e) => that.onSessionClick(session) :
                              null)}
                    href="#">
                    Playground: {session.id} [{session.state}]
                    <span className="badge">{session.kb?"kb ":""}</span>
                </a>
        });
        list = <div className="list-group">
                {listItems}
               </div>;
        let n = this.state.sessions.length;
        body =  <div>
                 <p style={{clear:"none", float:"left"}}>
                   There {n>1?"are":"is"} currently {n} active playground{n > 1?"s":""}.
                   Pick one to join or create a new one.
                </p>
                <div style={{float:"right", textAlign: "left"}}>
                    Legend:
                    <ul className="list-group">
                        <li className="list-group-item list-group-item-success">
                            Someone's active here.
                        </li>
                        <li className="list-group-item list-group-item-info">
                            Someone's playing here now.
                        </li>
                        <li className="list-group-item list-group-item-warning">
                            Session with a physical keyboard and no-one attached 
                            &nbsp;<span className="badge">kb</span>
                        </li>
                    </ul>
                </div>
               </div>;
    }

    return (
      <div className="panel panel-default">
            
        <div className="panel-heading">
          <h3 className="panel-title">
              Pick your playground
          </h3>
        </div>
        <div className="panel-body">
          {body}
        </div>
          {list}
          <div className="list-group">
            <a href="#"
                className="list-group-item list-group-item-success"
                onClick={(e) => this.onSessionClick({id: 'new'})}
                >
                Start a new playground
            </a>
          </div>
      </div>
    );
  }
}

class Main extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            session: null
        };
    }

    observeSession(session) {
        console.log("About to observe session " + session);
        this.setState({
            session: session
        });
    }

    cancelObservation() {
        this.observeSession(null);
    }

    render(){ 
        if (this.state.session === null) {
            return <SessionsList onSessionChosen={this.observeSession.bind(this)} />;
        }
        return (
            <div className="panel panel-default">
              <div className="panel-heading">
                <h3 className="panel-title">
                    Livecoding playground
                    &nbsp;
                    <a href="#" onClick={this.cancelObservation.bind(this)}>
                        <span className="label label-danger">
                          Leave
                        </span>
                    </a>
                </h3>
              </div>
              <div className="panel-body">
                <Observation session={this.state.session} />
              </div>
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
            mp3_url: null,
            lost_keyboard: false
        };
    }

    componentDidMount() {
        this.ws = new WebSocket("ws://" + window.location.host + "/observe/" + this.props.session.id);
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
                mp3_url: data.mp3.url,
                lost_keyboard: this.props.session.kb && !data.session.kb
            });
        }
    }

    render() {
        let body;
        if (!this.state.ssh_url) {
            body = (<div className="progress">
                       <div className="progress-bar progress-bar-success progress-bar-striped active" role="progressbar" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100" style={{width: "100%"}} >
                           Loading...
                       </div>
                     </div>
                    );
        } else {
            body = (
                    <div className="observation">
                      {this.state.lost_keyboard ?
                       <div class="alert alert-danger" role="alert">
                          The keyboard is lost :( Please reconnect to use external keyboard.
                       </div> : ""}
                      <MP3Player src={this.state.mp3_url} />
                      <SSHFrame src={this.state.ssh_url} />
                    </div>
            );
        }
        return  body;
    }
}

const domContainer = document.querySelector('#container');
ReactDOM.render(<Main />, domContainer);
